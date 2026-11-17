import sys
import os
from dotenv import load_dotenv
from pathlib import Path
import json
from langgraph.graph import StateGraph, START, END
from langgraph.errors import GraphRecursionError
from typing import TypedDict, Annotated
import operator
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
import asyncio
from collections.abc import AsyncGenerator
from langchain_openai import ChatOpenAI

CONFIG_PATH = Path(__file__).parent / "providers_config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

PROMPT = """你是公共事务问答助手，调用的大模型是智谱GLM，你的所有回答都要依据查询到的条目，
对于没有检索到资料的问题，严禁给出任何的建议或提示，严禁回答与公共事务无关的任何问题，直接回答“当前问题超出我的服务范围，无法为您提供帮助”"""


PYTHON = sys.executable
SERVER = Path(__file__).parent/"server.py"

load_dotenv(Path(__file__).parent / ".env")

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    session: ClientSession
    tools: list

graph = StateGraph(AgentState)

provider = os.getenv("PROVIDER", "deepseek")
key = os.getenv(f"{provider.upper()}_API_KEY")
if not key:
    raise ValueError("暂无API的key")

LLM = ChatOpenAI(api_key=key, base_url=PROVIDERS[provider]["base_url"], model=PROVIDERS[provider]["model"])

async def call_llm(state: AgentState):
    message = await LLM.bind_tools(state["tools"]).ainvoke(state["messages"])
    return {"messages":[message]}

async def run_tools(state: AgentState):
    msg = []
    tool_calls = state["messages"][-1].tool_calls
    for call in tool_calls:
        tc_id = call["id"]
        fun_name = call["name"]
        params = call["args"]
        print(f"工单 {fun_name} 参数 {params}")
        result = await state["session"].call_tool(fun_name, params)
        if result.is_error:
            print(f"调用函数 {fun_name}时出错")
        msg.append({
            "role":"tool",
            "tool_call_id":tc_id,
            "content":result.content[0].text
        })
    return {"messages":msg}

def should_continue(state: AgentState):
    if state["messages"][-1].tool_calls:
        return "again"
    return "end"

def get_tools(tool_list):
    tools = []
    for tool in tool_list.tools:
        tools.append({
            "type":"function",
            "function":{
                "name":tool.name,
                "description":tool.description,
                "parameters":tool.input_schema
            }
        })
    return tools

graph.add_node("call_llm", call_llm)
graph.add_node("run_tools", run_tools)
graph.add_edge(START, "call_llm")
graph.add_edge("run_tools", "call_llm")
graph.add_conditional_edges("call_llm", should_continue, {"again":"run_tools", "end":END})
app = graph.compile()

async def ask(question: str) -> AsyncGenerator[str, None]:
    if len(question) < 3:
        yield "问题太短了无法有效回答"
    else:
        params = StdioServerParameters(command=str(PYTHON), args=[str(SERVER)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tool_list = await session.list_tools()
                tools = get_tools(tool_list)
                try:
                    async for chunk, _ in app.astream({"messages":[{"role":"system", "content":PROMPT}, {"role":"user", "content":question}], "session":session, "tools":tools}, config={"recursion_limit":10}, stream_mode="messages"):
                        if chunk.content and not chunk.tool_call_chunks:
                            yield chunk.content
                except GraphRecursionError:
                    yield "轮次耗尽，换个问法重新试试吧"

async def main():
    async for res in ask("工伤保险待遇先行支付申请怎么操作？"):
        print(res, end="", flush=True)

if __name__ =="__main__":
    asyncio.run(main())
