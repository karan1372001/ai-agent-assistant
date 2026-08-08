from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import sqlite3
import re
import json
import math
import time
# time lets us pause briefly between retry attempts when searching

from datetime import datetime
from ddgs import DDGS
# This is a purpose-built tool for searching DuckDuckGo without triggering CAPTCHAs

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
# Sets up our memory database

for column in ["timestamp", "embedding"]:
    try:
        cursor.execute(f"ALTER TABLE history ADD COLUMN {column} TEXT")
        conn.commit()
    except Exception:
        pass
# Safety check for older database files missing these columns


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


def search_web(query):
    # Tool: does a REAL web search and returns real, current results
    # Includes automatic retries in case DuckDuckGo temporarily rate-limits us

    max_attempts = 3
    # Try up to 3 times before giving up

    for attempt in range(max_attempts):
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=3)
                # Ask DuckDuckGo for the top 3 results on this query

            if results:
                # Success! We got real results, so build and return them
                output = []
                for r in results:
                    title = r.get("title", "")
                    body = r.get("body", "")
                    output.append(f"{title}: {body}")
                return "\n".join(output)

            # If results were empty, wait a bit and try again
            time.sleep(2)

        except Exception as e:
            # If something went wrong (like a temporary block), wait and try again
            time.sleep(2)

    # If all attempts failed, give an honest answer instead of pretending
    return "I searched but couldn't retrieve results right now (search engine may be temporarily rate-limited). Please try again in a moment."


def get_embedding(text):
    # Converts text into a "meaning fingerprint" for smart memory search
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return response.json()["embedding"]


def cosine_similarity(a, b):
    # Measures how similar in meaning two fingerprints are
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0
    return dot / (mag_a * mag_b)


def find_relevant_memories(current_message, limit=5):
    # Searches ALL past messages for the ones most relevant to the current message
    current_embedding = get_embedding(current_message)

    cursor.execute("SELECT role, content, embedding FROM history WHERE embedding IS NOT NULL")
    all_rows = cursor.fetchall()

    scored = []
    for role, content, embedding_json in all_rows:
        if not embedding_json:
            continue
        stored_embedding = json.loads(embedding_json)
        score = cosine_similarity(current_embedding, stored_embedding)
        scored.append((score, role, content))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


SYSTEM_PROMPT = """You are a helpful assistant with access to tools and long-term memory.

RULE: If the user asks for the time, date, a math calculation, or wants you to search the internet 
for current information, you MUST respond with ONLY this exact format and nothing else:
TOOL: get_time()
or
TOOL: calculate(expression)
or
TOOL: search_web(query)

Use search_web whenever the user asks about something current, recent, or that you might not know.

Examples:
User: what's the latest news about AI?
You: TOOL: search_web(latest AI news)

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
    # Saves a message into the database, with its meaning fingerprint and timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        embedding = get_embedding(content)
        embedding_json = json.dumps(embedding)
    except Exception:
        embedding_json = None

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

    cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT 6")
    recent = cursor.fetchall()
    recent.reverse()

    relevant = find_relevant_memories(request.message, limit=5)

    memory_context = ""
    if relevant:
        memory_context = "Relevant memories from past conversations:\n"
        for score, role, content in relevant:
            memory_context += f"- {role}: {content}\n"

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + memory_context}]

    for role, content in recent:
        messages.append({"role": "user" if role == "user" else "assistant", "content": content})

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
        elif tool_name == "search_web":
            tool_result = search_web(tool_arg)
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