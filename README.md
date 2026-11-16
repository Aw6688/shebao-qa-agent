# shebao-qa-agent

社保政务问答 Agent：77 条公开政策知识卡 + LangGraph 状态图 + MCP 工具层 + FastAPI 服务。

一个"只答库内、库外拒答"的受限问答 Agent：检索工具由独立 MCP server 提供，LLM 通过多轮工具调用组织答案，超出知识范围的问题按模板拒答，不夹带模型自身知识。

## 架构

```
浏览器 / 终端
    │  HTTP POST /chat {"question": "..."}
    ▼
api.py（FastAPI，把 Agent 封装成服务）
    │  await ask(question)
    ▼
agent.py（LangGraph 状态图：call_model ⇄ run_tools）
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

## 核心设计决策

| 决策 | 理由 |
|---|---|
| LangGraph 而非手写 while 循环 | 递归闸门防死循环（recursion_limit=10，2 节点 × 5 轮；实测不设闸门会跑到 10007 步）；条件边做路由，状态合并交给 reducer |
| MCP 而非进程内函数 | 参数校验由 server 侧 pydantic `model_validate` 承担，主程序省掉一半防御代码；工具执行错误以 is_error 回执返回、不炸主流程 |
| 每请求独立 MCP 生命周期 | demo 规模下子进程现起现杀成本不到 1 秒，换来零会话管理复杂度 |
| 防线版 PROMPT | 身份声明（压制身份幻觉）+ 知识边界声明 + 拒答模板——堵不如疏：给模型一个"超范围该怎么办"的出口，它就不再夹带自身知识硬答 |

## 安全实测

本项目做过一轮系统性安全测试，以下数字均来自实测原始输出：

- **注入三连**（指令覆盖 / 提示词提取 / 角色越狱）：防住 2/3，被击穿的以拒答模板兜底
- **Prompt 保密性采样**（管理员话术 5 次）：5/5 全被提取，泄露呈翻译、逐字、重组三种形态 → 架构结论：**秘密不进 prompt**，防线移到最小权限与输出侧检测
- **数据投毒实验**：公文伪装的毒条目入库后，检索命中即完整发作，入口过滤、canary、模型侧判断全部绕过 → 架构结论：**入库治理是主防线**，守门在入库处，不在出口教模型鉴毒
- 现行防御四层：信任分级声明 / 入库治理（主防线）/ 输出侧检测 / 最小权限

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
uvicorn api:app                 # 浏览器打开 http://127.0.0.1:8000
```

## Roadmap

- [ ] 多轮会话历史
- [ ] 流式输出
- [ ] 输出侧 canary 检测

## 数据说明

77 条知识卡（标题 / 主项名称 / 子项名称 / 设定依据 / 申请材料清单 / 办理流程 等 13 字段）基于公开文件:【社会保险公共服务事项】，由 PyMuPDF 框线法自动抽取整理。数据仅用于学习演示，不构成任何办事依据；具体业务办理请以当地社保经办机构官方口径为准。
