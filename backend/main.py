from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up a simple database file to store chat history
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    content TEXT
)
""")
conn.commit()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"status": "Backend is running"}

@app.post("/chat")
def chat(request: ChatRequest):
    # Save the user's message into memory
    cursor.execute("INSERT INTO history (role, content) VALUES (?, ?)", ("user", request.message))
    conn.commit()

    # Get the last 10 messages so the AI remembers recent conversation
    cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT 10")
    recent = cursor.fetchall()
    recent.reverse()  # put them back in correct order (oldest to newest)

    # Build a conversation string to send to the AI
    conversation = ""
    for role, content in recent:
        conversation += f"{role}: {content}\n"

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1",
            "prompt": conversation,
            "stream": False
        }
    )
    result = response.json()
    ai_reply = result["response"]

    # Save the AI's reply into memory too
    cursor.execute("INSERT INTO history (role, content) VALUES (?, ?)", ("assistant", ai_reply))
    conn.commit()

    return {"reply": ai_reply}