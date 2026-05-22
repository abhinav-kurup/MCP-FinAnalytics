import os
import json
from typing import TypedDict, List, Dict, Any, Annotated
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import StructuredTool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from pydantic import create_model

from prompts import SYSTEM_PROMPT, REPORT_SYNTHESIS_PROMPT
from mcp_client import mcp_manager

class AgentState(TypedDict):
    query: str
    tickers: List[str]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    reasoning_steps: List[str]
    final_report: str
    error: str | None
    messages: List[Any]

def get_llm():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider == "anthropic":
        return ChatAnthropic(model="claude-3-5-sonnet-20240620")
    elif provider == "openai":
        return ChatOpenAI(model="gpt-4o-mini")
    elif provider == "groq":
        return ChatGroq(model="llama-3.3-70b-versatile")
    else:
        raise ValueError(f"Unknown provider: {provider}")

def _json_schema_to_pydantic_type(schema: dict):
    """Very basic conversion from JSON schema to python types for pydantic."""
    t = schema.get("type", "string")
    if t == "string":
        return str
    if t == "number":
        return float
    if t == "integer":
        return int
    if t == "boolean":
        return bool
    if t == "array":
        return list
    if t == "object":
        return dict
    return Any

async def create_langchain_tools() -> List[StructuredTool]:
    """Dynamically creates LangChain tools from the MCP tools"""
    mcp_tools = await mcp_manager.list_all_tools()
    lc_tools = []
    
    for tool_def in mcp_tools:
        server_name = tool_def["server_name"]
        tool_name = tool_def["name"]
        desc = tool_def["description"] or f"Tool {tool_name} from {server_name}"
        input_schema = tool_def["inputSchema"]
        
        # Build pydantic model dynamically
        fields = {}
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        for prop_name, prop_schema in properties.items():
            prop_type = _json_schema_to_pydantic_type(prop_schema)
            if prop_name in required:
                fields[prop_name] = (prop_type, ...)
            else:
                fields[prop_name] = (prop_type, None)
                
        args_schema = create_model(f"{tool_name}_args", **fields)
        
        def _create_run(s_name, t_name):
            async def _run(**kwargs):
                return await mcp_manager.call_tool(s_name, t_name, kwargs)
            return _run
            
        lc_tool = StructuredTool.from_function(
            func=None,
            coroutine=_create_run(server_name, tool_name),
            name=tool_name,
            description=desc,
            args_schema=args_schema
        )
        lc_tools.append(lc_tool)
        
    return lc_tools

async def reason_node(state: AgentState) -> dict:
    llm = get_llm()
    lc_tools = await create_langchain_tools()
    llm_with_tools = llm.bind_tools(lc_tools)
    
    # Initialize messages if empty
    messages = state.get("messages", [])
    if not messages:
        # Construct system prompt
        tool_cat = []
        for t in lc_tools:
            tool_cat.append(f"- {t.name}: {t.description}")
        sys_prompt = SYSTEM_PROMPT.format(tool_catalogue="\n".join(tool_cat))
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=state["query"])]
        
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)
    
    reasoning = []
    if response.content and isinstance(response.content, str):
        reasoning.append(response.content)
        
    return {"messages": messages, "reasoning_steps": state.get("reasoning_steps", []) + reasoning}

async def act_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    if not last_message.tool_calls:
        # Should not happen if routed here, but safe check
        return {"messages": messages}
        
    lc_tools = await create_langchain_tools()
    tool_map = {t.name: t for t in lc_tools}
    
    tool_results = state.get("tool_results", [])
    tool_calls_made = state.get("tool_calls", [])
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        tool_calls_made.append({
            "tool": tool_name,
            "args": tool_args
        })
        
        if tool_name in tool_map:
            try:
                result = await tool_map[tool_name].ainvoke(tool_args)
                tool_results.append({
                    "tool": tool_name,
                    "result": result
                })
                # Add tool message
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": json.dumps(result)
                })
            except Exception as e:
                tool_results.append({"tool": tool_name, "error": str(e)})
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": f"Error: {str(e)}"
                })
        else:
            messages.append({
                "role": "tool",
                "name": tool_name,
                "tool_call_id": tool_id,
                "content": f"Error: Tool {tool_name} not found"
            })
            
    return {"messages": messages, "tool_results": tool_results, "tool_calls": tool_calls_made}

async def synthesise_node(state: AgentState) -> dict:
    llm = get_llm()
    
    results_str = json.dumps(state.get("tool_results", []), indent=2)
    prompt = REPORT_SYNTHESIS_PROMPT.format(
        tool_results=results_str,
        query=state["query"]
    )
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"final_report": response.content}

def router(state: AgentState) -> str:
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    if getattr(last_message, "tool_calls", None):
        return "act"
    return "synthesise"

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("reason", reason_node)
    builder.add_node("act", act_node)
    builder.add_node("synthesise", synthesise_node)
    
    builder.set_entry_point("reason")
    builder.add_conditional_edges("reason", router)
    builder.add_edge("act", "reason")
    builder.add_edge("synthesise", END)
    
    return builder.compile()

# Singleton graph
agent_graph = build_graph()
