from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import sqlite3
import re
import json
import math
from datetime import datetime

app = FastAPI()
# Create our backend app

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Lets our webpage talk to this backend safely

conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    content TEXT,
    timestamp TEXT,
    embedding TEXT
)
""")
conn.commit()
# Sets up our memory database - now with an extra "embedding" column
# This will store each message's "meaning fingerprint" for smart search

# Safety check: adds missing columns if this is an older database file
for column in ["timestamp", "embedding"]:
    try:
        cursor.execute(f"ALTER TABLE history ADD COLUMN {column} TEXT")
        conn.commit()
    except Exception:
        pass


class ChatRequest(BaseModel):
    message: str
# What a normal text message looks like

class ImageChatRequest(BaseModel):
    message: str
    image_base64: str
# What a message with an image looks like


def get_time():
    return datetime.now().strftime("%I:%M %p on %B %d, %Y")
# Tool: returns the real current time

def calculate(expression):
    try:
        if re.match(r'^[0-9+\-*/(). ]+$', expression):
            result = eval(expression)
            return str(result)
        else:
            return "Invalid expression"
    except Exception:
        return "Error calculating that"
# Tool: solves basic math safely


def get_embedding(text):
    # Turns any piece of text into a list of numbers that represents its MEANING
    # Similar meaning = similar numbers, even if the words are totally different
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return response.json()["embedding"]


def cosine_similarity(a, b):
    # Compares two "meaning fingerprints" and returns how similar they are
    # 1.0 = basically identical meaning, 0.0 = completely unrelated
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0
    return dot / (mag_a * mag_b)


def find_relevant_memories(current_message, limit=5):
    # This is the "smart search" - looks through EVERY past message ever saved
    # and finds the ones most relevant to what you just said, no matter how old

    current_embedding = get_embedding(current_message)
    # Get the meaning fingerprint of your new message

    cursor.execute("SELECT role, content, embedding FROM history WHERE embedding IS NOT NULL")
    all_rows = cursor.fetchall()
    # Grab every past message that has a saved fingerprint

    scored = []
    for role, content, embedding_json in all_rows:
        if not embedding_json:
            continue
        stored_embedding = json.loads(embedding_json)
        score = cosine_similarity(current_embedding, stored_embedding)
        scored.append((score, role, content))
    # Compare your new message against every old one, and score how related they are

    scored.sort(key=lambda x: x[0], reverse=True)
    # Put the most relevant matches first

    return scored[:limit]
    # Return only the top few most relevant memories


SYSTEM_PROMPT = """You are a helpful assistant with access to tools and long-term memory.

RULE: If the user asks for the time, date, or a math calculation, you MUST respond with ONLY this exact format and nothing else:
TOOL: get_time()
or
TOOL: calculate(expression)

You may also be given "Relevant memories" from past conversations. Use them naturally if helpful, 
but don't mention that you're using stored memories - just respond naturally, like you remember.

For anything else, just respond normally as a helpful assistant.
"""


def ask_ollama_chat(messages):
    # Sends a conversation to our text AI model and gets its reply
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": "llama3.1", "messages": messages, "stream": False}
    )
    return response.json()["message"]["content"]


def save_message(role, content):
    # Saves a message into the database, WITH its meaning fingerprint and timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        embedding = get_embedding(content)
        embedding_json = json.dumps(embedding)
    except Exception:
        embedding_json = None
    # If embedding fails for some reason, we still save the message, just without search capability

    cursor.execute(
        "INSERT INTO history (role, content, timestamp, embedding) VALUES (?, ?, ?, ?)",
        (role, content, timestamp, embedding_json)
    )
    conn.commit()


@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.post("/chat")
def chat(request: ChatRequest):
    save_message("user", request.message)
    # Save your new message (this also creates its fingerprint)

    # Get the last 6 messages, for natural short-term conversation flow
    cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT 6")
    recent = cursor.fetchall()
    recent.reverse()

    # Get relevant OLD memories, even from way back, based on meaning
    relevant = find_relevant_memories(request.message, limit=5)

    memory_context = ""
    if relevant:
        memory_context = "Relevant memories from past conversations:\n"
        for score, role, content in relevant:
            memory_context += f"- {role}: {content}\n"
    # Build a small summary of relevant past info to give the AI extra context

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + memory_context}]

    for role, content in recent:
        messages.append({"role": "user" if role == "user" else "assistant", "content": content})
    # Add the recent conversation on top, so it flows naturally

    ai_reply = ask_ollama_chat(messages)

    # Check if the AI wants to use a tool
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


@app.post("/chat-image")
def chat_image(request: ImageChatRequest):
    save_message("user", request.message + " [sent an image]")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llava",
            "prompt": request.message,
            "images": [request.image_base64],
            "stream": False
        }
    )
    result = response.json()

    if "response" not in result:
        return {"reply": f"Error from vision model: {result}"}

    ai_reply = result["response"]
    save_message("assistant", ai_reply)

    return {"reply": ai_reply}


@app.get("/history")
def get_history():
    cursor.execute("SELECT role, content, timestamp FROM history ORDER BY id ASC")
    rows = cursor.fetchall()
    return {
        "history": [
            {"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows
        ]
    }