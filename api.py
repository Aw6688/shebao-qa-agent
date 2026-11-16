from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from agent import ask
import uvicorn

class ChatRequest(BaseModel):
    question: str = Field(
        ..., description="用户输入的问题"
    )

class ChatResponse(BaseModel):
    answer: str = Field(
        ..., description="调用问答系统的结果"
    )

app = FastAPI(title="公共事务助手", version="1.0")

@app.post("/chat", response_model=ChatResponse)
async def chat(param: ChatRequest):
    return ChatResponse(
        answer=await ask(param.question)
    )

app.mount("/", StaticFiles(directory="static", html=True))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020)