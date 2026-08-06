from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"status": "Backend is running"}

@app.post("/chat")
def chat(request: ChatRequest):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1",
            "prompt": request.message,
            "stream": False
        }
    )
    result = response.json()
    return {"reply": result["response"]}