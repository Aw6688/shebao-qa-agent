from agent import ask
from pydantic import Field, BaseModel
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import uvicorn
import json

class ChatRequest(BaseModel):
    question: str = Field(
        ..., description="用户输入的问题"
    )

app = FastAPI(title="shebao_stream", version="1.1")

async def stream_answer(question: str):
    async for content in ask(question):
        yield "data: " + json.dumps({"token":content}, ensure_ascii=False) + "\n\n"

@app.post("/chat")
async def chat(param: ChatRequest):
    return StreamingResponse(stream_answer(param.question), media_type="text/event-stream")

app.mount("/", StaticFiles(directory="static", html=True))

if __name__ == "__main__":
    uvicorn.run(app=app, host="127.0.0.1", port=8020)