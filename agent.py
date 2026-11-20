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
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

CONFIG_PATH = Path(__file__).parent / "providers_config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    PROVIDERS = json.load(f)

PROMPT = """你是公共事务问答助手，调用的大模型是智谱GLM，你的所有回答都要依据查询到的条目，对于模糊的问题必须先跟用户澄清；
对于没有检索到资料的问题，严禁给出任何的建议或提示，严禁回答与公共事务无关的任何问题，直接回答“当前问题超出我的服务范围，无法为您提供帮助”"""

PYTHON = sys.executable
SERVER = Path(__file__).parent/"server.py"

provider = os.getenv("PROVIDER", "zhipu")
key = os.getenv(f"{provider.upper()}_API_KEY")
if not key:
    raise ValueError("请先配置一个模型API的key")
LLM = ChatOpenAI(api_key=key, base_url=PROVIDERS[provider]["base_url"], model=PROVIDERS[provider]["model"])

HISTORY_MAP = {}
MAX_TOKEN = 2000

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    tools: list
    session: ClientSession

async def call_llm(state: AgentState):
    result = await LLM.bind_tools(state["tools"]).ainvoke(state["messages"])
    return {"messages":[result]}

async def run_tools(state: AgentState):
    messages = []
    tool_calls = state["messages"][-1].tool_calls
    for tc in tool_calls:
        id = tc["id"]
        fun_name = tc["name"]
        params = tc["args"]
        tool_res = await state["session"].call_tool(fun_name, params)
        messages.append({
            "role": "tool",
            "tool_call_id": id,
            "content": tool_res.content[0].text
        })
    return {"messages":messages}

def should_continue(state: AgentState):
    messages = state["messages"][-1]
    if messages.tool_calls:
        return "again"
    return "end"

graph = StateGraph(AgentState)
graph.add_node("call_llm", call_llm)
graph.add_node("run_tools", run_tools)
graph.add_edge(START, "call_llm")
graph.add_edge("run_tools", "call_llm")
graph.add_conditional_edges("call_llm", should_continue, {"end":END, "again":"run_tools"})
app = graph.compile()

def get_tools(tools_list):
    tools = []
    for tool in tools_list.tools:
        tools.append({
            "type":"function",
            "function":{
                "name":tool.name,
                "description":tool.description,
                "parameters":tool.input_schema
            }
        })
    return tools

def handle_history(history):
    num, result = 0, []
    if history:
        for msg in reversed(history):
            if num + len(msg["content"]) > MAX_TOKEN:
                break
            result.append(msg)
            num += len(msg["content"])
        result.reverse()
    return result

def build_message(question: str, trimmed: list):
    messages = [SystemMessage(PROMPT)]
    for msg in trimmed:
        if msg["role"] == "user":
            messages.append(HumanMessage(msg["content"]))
        else:
            messages.append(AIMessage(msg["content"]))
    messages.append(HumanMessage(question))
    return messages

async def ask(question: str, session_id: str):
    if len(question) < 3:
        yield "问题太短啦，无法回答"
    else:
        history = HISTORY_MAP.get(session_id, [])
        trimmed = handle_history(history)
        params = StdioServerParameters(command=str(PYTHON), args=[str(SERVER)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_list = await session.list_tools()
                tools = get_tools(tools_list)
                answer = ""
                try:
                    async for chunk, _ in app.astream({"messages":build_message(question, trimmed), "session":session, "tools":tools},config={"recursion_limit":10}, stream_mode="messages"):
                        if chunk.content and not chunk.tool_call_chunks:
                            answer += chunk.content
                            yield chunk.content
                except GraphRecursionError:
                    yield "轮次耗尽啦，换个问法试试吧"
                HISTORY_MAP[session_id] = history + [
                    {"role":"user", "content":question},
                    {"role":"assistant", "content": answer}
                ]

async def main():
    async for con in ask("工伤保险待遇先行支付申请怎么操作？", "aw"):
        print(con, end="", flush=True)
if __name__ == "__main__":
    asyncio.run(main())



