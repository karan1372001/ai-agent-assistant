from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import sqlite3
import re
import json
import math
import time
import os
import webbrowser
import subprocess
import uuid
from datetime import datetime
from ddgs import DDGS
import pywhatkit

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
    timestamp TEXT,
    embedding TEXT
)
""")
conn.commit()

for column in ["timestamp", "embedding"]:
    try:
        cursor.execute(f"ALTER TABLE history ADD COLUMN {column} TEXT")
        conn.commit()
    except Exception:
        pass


class ChatRequest(BaseModel):
    message: str

class ImageChatRequest(BaseModel):
    message: str
    image_base64: str

class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool


PENDING_ACTIONS = {}
# Each pending action can now hold a LIST of remaining steps, not just one
# This lets us chain multiple actions together, one approval at a time


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


def search_web(query):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=3)
            if results:
                output = []
                for r in results:
                    title = r.get("title", "")
                    body = r.get("body", "")
                    output.append(f"{title}: {body}")
                return "\n".join(output)
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return "I searched but couldn't retrieve results right now. Please try again in a moment."


def open_app(app_name):
    try:
        os.system(f"start {app_name}")
        return f"Opened {app_name}"
    except Exception as e:
        return f"Failed to open {app_name}: {e}"

def open_website(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed to open website: {e}"

def play_youtube(song_name):
    try:
        pywhatkit.playonyt(song_name)
        return f"Playing '{song_name}' on YouTube"
    except Exception as e:
        return f"Failed to play song: {e}"

def open_folder(path):
    try:
        os.startfile(path)
        return f"Opened folder: {path}"
    except Exception as e:
        return f"Failed to open folder: {e}"


def determine_file_extension(description):
    description_lower = description.lower()
    if "c language" in description_lower or " c " in description_lower or description_lower.startswith("c "):
        return ".c"
    elif "python" in description_lower:
        return ".py"
    elif "javascript" in description_lower or "js" in description_lower:
        return ".js"
    elif "java" in description_lower:
        return ".java"
    elif "html" in description_lower:
        return ".html"
    else:
        return ".txt"


def determine_opener_app(description):
    description_lower = description.lower()
    if "vs code" in description_lower or "vscode" in description_lower or "visual studio code" in description_lower:
        return "vscode"
    elif "notepad" in description_lower:
        return "notepad"
    else:
        return "notepad"


def create_and_open_file(content, description):
    try:
        extension = determine_file_extension(description)
        filename = f"generated_file{extension}"
        folder = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(folder, filename)

        with open(filepath, "w") as f:
            f.write(content)

        opener = determine_opener_app(description)

        if opener == "vscode":
            subprocess.Popen(["code", filepath], shell=True)
            app_used = "VS Code"
        else:
            subprocess.Popen(["notepad.exe", filepath])
            app_used = "Notepad"

        return f"Created {filename} on your Desktop and opened it in {app_used}"
    except Exception as e:
        return f"Failed to create file: {e}"


COMPUTER_CONTROL_TOOLS = ["open_app", "open_website", "play_youtube", "open_folder", "create_file"]


def get_embedding(text):
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return response.json()["embedding"]


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0
    return dot / (mag_a * mag_b)


def find_relevant_memories(current_message, limit=5):
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


SYSTEM_PROMPT = """You are a helpful assistant with access to tools, long-term memory, and computer control.

RULE: To use a tool, respond with ONLY tool lines in this exact format, one per line, nothing else:
TOOL: tool_name(argument)

If the user's request needs MULTIPLE actions done in order, output MULTIPLE tool lines, one per line, 
in the order they should happen. For example, if the user wants two things done, write two TOOL lines.

Available tools:
- get_time() -> current date and time
- calculate(expression) -> basic math
- search_web(query) -> search the internet for current info
- open_app(app_name) -> opens an application
- open_website(url) -> opens a website
- play_youtube(song_name) -> searches and plays a video on YouTube (this already opens the browser, 
  do NOT also use open_app or open_website before it)
- open_folder(path) -> opens an EXISTING folder to browse files
- create_file(description) -> writes code/content to a file and opens it in notepad or vscode 
  (include "open in notepad" or "open in vscode" in the description if specified)

Examples:
User: open chrome
You: TOOL: open_app(chrome)

User: play gta 6 trailer on youtube
You: TOOL: play_youtube(gta 6 trailer)

User: write python code and open it in vscode, then also open my documents folder
You: TOOL: create_file(python code, open in vscode)
TOOL: open_folder(C:\\Users\\KARAN\\Documents)

You may also be given "Relevant memories" from past conversations. Use them naturally.

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


def create_permission_request(steps):
    # steps = a list of (tool_name, tool_arg) tuples that still need to happen
    # We ask permission for the FIRST one, and remember the rest for later

    first_tool_name, first_tool_arg = steps[0]
    remaining_steps = steps[1:]

    content_for_file = None
    if first_tool_name == "create_file":
        content_prompt = [
            {"role": "system", "content": f"Write ONLY the raw code/content for: {first_tool_arg}. No explanation, no markdown, no backticks."},
            {"role": "user", "content": first_tool_arg}
        ]
        content_for_file = ask_ollama_chat(content_prompt)

    action_id = str(uuid.uuid4())
    PENDING_ACTIONS[action_id] = {
        "tool_name": first_tool_name,
        "tool_arg": first_tool_arg,
        "content": content_for_file,
        "remaining_steps": remaining_steps,
    }

    description = f"{first_tool_name}({first_tool_arg})"
    step_info = f" (step 1 of {len(steps)})" if len(steps) > 1 else ""

    if first_tool_name == "create_file":
        preview = content_for_file[:150] + ("..." if len(content_for_file) > 150 else "")
        reply = f"I'd like to create a file with this content{step_info}:\n\n{preview}\n\nDo you approve?"
    else:
        reply = f"I'd like to: {description.replace('_', ' ')}{step_info}. Do you approve this action?"

    save_message("assistant", f"[Requested permission for: {description}]")

    return {
        "needs_permission": True,
        "action_id": action_id,
        "description": description,
        "reply": reply
    }


def run_single_tool(tool_name, tool_arg, content=None):
    # Actually executes ONE approved action
    if tool_name == "open_app":
        return open_app(tool_arg)
    elif tool_name == "open_website":
        return open_website(tool_arg)
    elif tool_name == "play_youtube":
        return play_youtube(tool_arg)
    elif tool_name == "open_folder":
        return open_folder(tool_arg)
    elif tool_name == "create_file":
        return create_and_open_file(content, tool_arg)
    else:
        return "Unknown tool"


@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.post("/chat")
def chat(request: ChatRequest):
    save_message("user", request.message)

    # SHORTCUT: reliably catch "play ___ on youtube" without relying on AI guessing
    play_match = re.search(r"play (.+?) on youtube", request.message, re.IGNORECASE)
    if play_match:
        song_name = play_match.group(1)
        return create_permission_request([("play_youtube", song_name)])

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

    # Find ALL tool calls in the reply, not just the first one - this enables multi-step actions
    tool_matches = re.findall(r"TOOLS?:\s*(\w+)\((.*)\)", ai_reply)

    if tool_matches:
        computer_steps = []
        tool_results = []

        for tool_name, tool_arg in tool_matches:
            if tool_name in COMPUTER_CONTROL_TOOLS:
                computer_steps.append((tool_name, tool_arg))
            elif tool_name == "get_time":
                tool_results.append(get_time())
            elif tool_name == "calculate":
                tool_results.append(calculate(tool_arg))
            elif tool_name == "search_web":
                tool_results.append(search_web(tool_arg))

        # If there are computer-control steps, ask permission for them (chained)
        if computer_steps:
            return create_permission_request(computer_steps)

        # Otherwise, all tools were safe ones - reply naturally using their results
        if tool_results:
            messages.append({"role": "assistant", "content": ai_reply})
            messages.append({"role": "user", "content": f"Tool results: {'; '.join(tool_results)}. Now reply to me naturally using these results."})
            ai_reply = ask_ollama_chat(messages)

    save_message("assistant", ai_reply)
    return {"reply": ai_reply, "needs_permission": False}


@app.post("/approve-action")
def approve_action(request: ApprovalRequest):
    action = PENDING_ACTIONS.get(request.action_id)

    if not action:
        return {"reply": "This action has expired or doesn't exist anymore."}

    if not request.approved:
        del PENDING_ACTIONS[request.action_id]
        save_message("assistant", "Action was denied by the user. Remaining steps cancelled.")
        return {"reply": "Okay, I won't do that. I've also cancelled any remaining steps."}

    tool_name = action["tool_name"]
    tool_arg = action["tool_arg"]
    content = action.get("content")
    remaining_steps = action.get("remaining_steps", [])

    tool_result = run_single_tool(tool_name, tool_arg, content)
    del PENDING_ACTIONS[request.action_id]

    save_message("assistant", f"Action approved and completed: {tool_result}")

    # If there are more steps left, ask permission for the NEXT one now
    if remaining_steps:
        next_request = create_permission_request(remaining_steps)
        next_request["reply"] = f"{tool_result}\n\nNext: {next_request['reply']}"
        return next_request

    # No more steps - we're fully done
    return {"reply": tool_result, "needs_permission": False}


@app.post("/chat-image")
def chat_image(request: ImageChatRequest):
    save_message("user", request.message + " [sent an image]")
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "llava", "prompt": request.message, "images": [request.image_base64], "stream": False}
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
    return {"history": [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]}