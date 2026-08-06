from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import sqlite3
import re
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# ---------- TOOLS ----------

def get_time():
    return datetime.now().strftime("%I:%M %p on %B %d, %Y")

def calculate(expression):
    try:
        if re.match(r'^[0-9+\-*/(). ]+$', expression):
            result = eval(expression)
            return str(result)
        else:
            return "Invalid expression"
    except Exception:
        return "Error calculating that"


SYSTEM_PROMPT = """You are a helpful assistant with access to tools.

RULE: If the user asks for the time, date, or a math calculation, you MUST respond with ONLY this exact format and nothing else:
TOOL: get_time()
or
TOOL: calculate(expression)

Examples:
User: what time is it?
You: TOOL: get_time()

User: what's 12 times 4?
You: TOOL: calculate(12*4)

For anything else, just respond normally as a helpful assistant.
"""

def ask_ollama_chat(messages):
    # Uses Ollama's proper chat endpoint (better instruction-following than raw text)
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "llama3.1",
            "messages": messages,
            "stream": False
        }
    )
    return response.json()["message"]["content"]


@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.post("/chat")
def chat(request: ChatRequest):
    cursor.execute("INSERT INTO history (role, content) VALUES (?, ?)", ("user", request.message))
    conn.commit()

    cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT 10")
    recent = cursor.fetchall()
    recent.reverse()

    # Build a proper messages list (system + user/assistant history)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in recent:
        messages.append({"role": "user" if role == "user" else "assistant", "content": content})

    ai_reply = ask_ollama_chat(messages)

    tool_match = re.search(r"TOOL:\s*(\w+)\((.*)\)", ai_reply)

    if tool_match:
        tool_name = tool_match.group(1)
        tool_arg = tool_match.group(2)

        if tool_name == "get_time":
            tool_result = get_time()
        elif tool_name == "calculate":
            tool_result = calculate(tool_arg)
        else:
            tool_result = "Unknown tool"

        # Give the AI the real result and ask for a natural reply
        messages.append({"role": "assistant", "content": ai_reply})
        messages.append({"role": "user", "content": f"Tool result: {tool_result}. Now reply to me naturally using this result."})

        ai_reply = ask_ollama_chat(messages)

    cursor.execute("INSERT INTO history (role, content) VALUES (?, ?)", ("assistant", ai_reply))
    conn.commit()

    return {"reply": ai_reply}