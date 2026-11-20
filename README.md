# shebao-qa-agent

一个社保政务问答 Agent。知识库是 77 条从公开政策文件里抽出来的知识卡，后端用 LangGraph 搭状态图，检索工具由独立的 MCP server 提供，FastAPI 包成 HTTP 服务，已支持 SSE 流式输出。

这个 Agent 只答库内的问题：模型通过多轮工具调用组织答案，超出知识范围就按模板拒答，不让它夹带自己的知识硬答。

## 架构

```
浏览器 / 终端
    │  HTTP POST /chat {"question": "..."}
    ▼
api.py（FastAPI，把 Agent 封装成服务）
    │  async for token in ask(question)
    ▼
agent.py（LangGraph 状态图：call_llm ⇄ run_tools）
    │                      │
    │ MCP 协议（stdio）     │ OpenAI 兼容接口
    ▼                      ▼
server.py（MCP server）    智谱 GLM
    │
    ▼
SQLite（data/demo.db：77 条知识卡 × 13 字段）
```

MCP server 对外提供两个工具：

- `search_cards(keyword)` —— 关键词检索，返回命中的卡列表（id + 标题）
- `get_card_by_id(card_id)` —— 按编号取整卡详情

## 为什么这么做

几个主要选型，都是踩过坑之后才定的：

- **LangGraph 而不是手写 while 循环**：一开始也觉得上框架重，实际两个节点加条件边就搭完了。递归闸门（recursion_limit=10）解决死循环——实测不设闸门会跑到 10007 步。状态合并交给 reducer，不用自己拼消息列表。
- **MCP 而不是进程内函数**：工具参数校验放在 server 侧（pydantic model_validate），主程序省掉一半防御代码；工具报错以 is_error 回执返回，不炸主流程。
- **每次请求现起现杀 MCP 子进程**：demo 规模下成本不到 1 秒，换来零会话管理——比做连接池简单太多。
- **PROMPT 里写清拒答模板**：跟模型说"超范围就这么答"，比堵着它不许答管用，实测它就不夹带私货了。

## 安全实测

以下都是实际跑出来的，不是理论推演：

- 指令覆盖 / 提示词提取 / 角色越狱三个注入：防住 2/3，被击穿的靠拒答模板兜底
- 管理员话术套 prompt，试了 5 次，5 次全成功，泄露形态有逐字、翻译、重组三种 → 所以秘密不能放进 prompt，防线移到最小权限和输出侧
- 数据投毒：把伪装成公文的毒条目塞进库，检索命中就完整发作，入口过滤、canary、模型侧判断全都拦不住 → 结论：入库治理才是主防线，守在出口是没用的
- 目前的防御：信任分级声明 / 入库治理 / 输出侧检测 / 最小权限

## 快速开始

```bash
git clone https://github.com/Aw6688/shebao-qa-agent.git
cd shebao-qa-agent

python -m venv .venv
.venv\Scripts\activate          # Windows；Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

python load_db.py               # data/cards.json → data/demo.db
copy .env.example .env          # Linux/Mac: cp .env.example .env，填入你的 API Key

# 方式一：终端问答
python agent.py

# 方式二：网页 Demo
python api.py                   # 浏览器打开 http://127.0.0.1:8020（SSE 流式输出）
```

## Docker 运行（可选）

```bash
docker build -t shebao-qa:1 .
docker run --rm -p 8020:8020 --env-file .env shebao-qa:1
# 浏览器打开 http://localhost:8020/page
```

## Roadmap

- [x] 多轮会话历史
- [x] 流式输出（agent astream messages + api SSE 信封 + 前端 reader 增量渲染）
- [ ] 输出侧 canary 检测

## 数据说明

77 条知识卡（标题 / 主项名称 / 子项名称 / 设定依据 / 申请材料清单 / 办理流程 等 13 字段）基于公开文件:【社会保险公共服务事项】，由 PyMuPDF 框线法自动抽取整理。数据仅用于学习演示，不构成任何办事依据；具体业务办理请以当地社保经办机构官方口径为准。
