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
    session_id: str = Field(
        ..., description="身份标识，唯一"
    )

app = FastAPI(title="shebao-Q&A", version="1.1")
app.mount("/page", StaticFiles(directory="static", html=True), name="page")

async def stream_answer(question: str, session_id: str):
    async for content in ask(question, session_id):
        yield "data: " + json.dumps({"token": content}, ensure_ascii=False) + "\n\n"

@app.post("/chat")
async def chat(params: ChatRequest):
    return StreamingResponse(stream_answer(params.question, params.session_id), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020)