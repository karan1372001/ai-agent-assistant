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
    content TEXT,
    timestamp TEXT
)
""")
conn.commit()

# If the table already existed WITHOUT a timestamp column, add it safely
try:
    cursor.execute("ALTER TABLE history ADD COLUMN timestamp TEXT")
    conn.commit()
except Exception:
    pass  # column already exists, ignore

class ChatRequest(BaseModel):
    message: str


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
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": "llama3.1", "messages": messages, "stream": False}
    )
    return response.json()["message"]["content"]


def save_message(role, content):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO history (role, content, timestamp) VALUES (?, ?, ?)",
        (role, content, timestamp)
    )
    conn.commit()


@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.post("/chat")
def chat(request: ChatRequest):
    save_message("user", request.message)

    cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT 10")
    recent = cursor.fetchall()
    recent.reverse()

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

        messages.append({"role": "assistant", "content": ai_reply})
        messages.append({"role": "user", "content": f"Tool result: {tool_result}. Now reply to me naturally using this result."})

        ai_reply = ask_ollama_chat(messages)

    save_message("assistant", ai_reply)

    return {"reply": ai_reply}


@app.get("/history")
def get_history():
    # Returns ALL past messages with their timestamps, oldest first
    cursor.execute("SELECT role, content, timestamp FROM history ORDER BY id ASC")
    rows = cursor.fetchall()
    return {
        "history": [
            {"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows
        ]
    }