# =============================================================================
#  KARAN'S AI ASSISTANT - BACKEND (main.py)
#  This file runs the "brain" of the assistant: it talks to Ollama (the AI
#  models running on your own PC), remembers past conversations, can search
#  the web, can control your computer (with your permission), and understands
#  images.
# =============================================================================

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
from zoneinfo import ZoneInfo
from ddgs import DDGS
import pywhatkit

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# DATABASE SETUP
# -----------------------------------------------------------------------------
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


# =============================================================================
# FACTS SYSTEM
# =============================================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS facts (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")
conn.commit()


def save_fact(key, value):
    cursor.execute("INSERT OR REPLACE INTO facts (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_all_facts():
    cursor.execute("SELECT key, value FROM facts")
    return cursor.fetchall()


def detect_and_save_facts(message):
    message_lower = message.lower()

    lang_match = re.search(r"favou?rite (?:programming |coding )?language is (\w+)", message_lower)
    if lang_match:
        save_fact("favorite_language", lang_match.group(1).capitalize())

    name_match = re.search(r"my name is (\w+)", message_lower)
    if name_match:
        save_fact("name", name_match.group(1).capitalize())

    fullname_match = re.search(r"my full name is ([\w\s]+)", message_lower)
    if fullname_match:
        save_fact("full_name", fullname_match.group(1).strip().title())

    nickname_match = re.search(r"(?:call me|my nickname is) (\w+)", message_lower)
    if nickname_match:
        save_fact("nickname", nickname_match.group(1).upper())


# =============================================================================
# SIMPLE TOOLS
# =============================================================================

TIMEZONE_MAP = {
    "uk": "Europe/London",
    "united kingdom": "Europe/London",
    "england": "Europe/London",
    "london": "Europe/London",
    "india": "Asia/Kolkata",
    "usa": "America/New_York",
    "us": "America/New_York",
    "united states": "America/New_York",
    "new york": "America/New_York",
    "california": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles",
    "japan": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",
    "australia": "Australia/Sydney",
    "sydney": "Australia/Sydney",
    "dubai": "Asia/Dubai",
    "uae": "Asia/Dubai",
    "germany": "Europe/Berlin",
    "france": "Europe/Paris",
    "canada": "America/Toronto",
    "singapore": "Asia/Singapore",
}


def get_time(location=None):
    if location:
        location_key = location.strip().lower()
        tz_name = TIMEZONE_MAP.get(location_key)
        if tz_name:
            now = datetime.now(ZoneInfo(tz_name))
            return now.strftime("%I:%M %p on %B %d, %Y") + f" ({location.strip()} time)"
        else:
            return f"I don't have timezone data for '{location.strip()}' yet, so I can't give an exact local time for it."

    return datetime.now().strftime("%I:%M %p on %B %d, %Y") + " (your local time)"


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


# =============================================================================
# COMPUTER CONTROL TOOLS
# =============================================================================

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


def extract_custom_path(description):
    path_match = re.search(r'[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\?)+', description)
    if path_match:
        return path_match.group(0).rstrip("\\")
    return None


def extract_custom_filename(description):
    match = re.search(
        r'(?:save(?: it| this)?\s+as|name(?:d)?\s+it|call(?:ed)?\s+it)\s+'
        r'([a-zA-Z0-9_\-. ]+?)(?=\s+(?:in|at|on|to)\b|[,]|$)',
        description,
        re.IGNORECASE
    )
    if not match:
        return None

    captured = match.group(1).strip()
    captured = re.sub(r'\s+name$', '', captured, flags=re.IGNORECASE)
    return captured.replace(" ", "_")


def create_and_open_file(content, description):
    try:
        custom_filename = extract_custom_filename(description)

        if custom_filename:
            has_extension = re.search(r'\.[a-zA-Z0-9]{1,10}$', custom_filename)
            if has_extension:
                filename = custom_filename
            else:
                extension = determine_file_extension(description)
                filename = f"{custom_filename}{extension}"
        else:
            extension = determine_file_extension(description)
            filename = f"generated_file{extension}"

        custom_path = extract_custom_path(description)
        if custom_path:
            folder = custom_path
            os.makedirs(folder, exist_ok=True)
        else:
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

        return f"Created {filename} in {folder} and opened it in {app_used}"
    except Exception as e:
        return f"Failed to create file: {e}"


COMPUTER_CONTROL_TOOLS = ["open_app", "open_website", "play_youtube", "open_folder", "create_file"]

# THE CHAINING FIX: how many rounds of "AI asks for a tool -> we run it ->
# AI replies again" we allow in a single request, before giving up. This
# stops raw, un-executed "TOOL: ..." text from ever reaching your screen.
MAX_TOOL_ROUNDS = 4


# =============================================================================
# SMART LONG-TERM MEMORY
# =============================================================================

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


# =============================================================================
# THE AI'S "PERSONALITY" AND INSTRUCTIONS
# =============================================================================

SYSTEM_PROMPT = """You are a helpful assistant with access to tools, long-term memory, and computer control.

RULE: To use a tool, respond with ONLY tool lines in this exact format, one per line, nothing else:
TOOL: tool_name(argument)

If the user's request needs MULTIPLE actions done in order, output MULTIPLE tool lines, one per line, 
in the order they should happen.

Available tools:
- get_time() -> current date and time where YOU are. get_time(location) -> the accurate current
  time in another place, e.g. get_time(UK) or get_time(India). ALWAYS use this tool for any
  question about the current time or date, anywhere - NEVER use search_web for time/date questions,
  since web search results can be old and give the wrong answer.
- calculate(expression) -> basic math
- search_web(query) -> search the internet for current info (news, facts, weather, etc - NOT for
  telling the time)
- open_app(app_name) -> opens an application
- open_website(url) -> opens a website
- play_youtube(song_name) -> searches and plays a video on YouTube
- open_folder(path) -> opens an EXISTING folder to browse files
- create_file(description) -> writes code/content to a file and opens it in notepad or vscode.
  If the user gives a filename (e.g. "save it as KD.html" or "save it as Karan")
  or a folder path (e.g. "E:\\MyFolder"), include that exact wording in the
  description so it gets saved with the right name and in the right place.

Examples:
User: open chrome
You: TOOL: open_app(chrome)

User: what time is it in the UK
You: TOOL: get_time(UK)

User: play gta 6 trailer on youtube
You: TOOL: play_youtube(gta 6 trailer)

User: write python code and open it in vscode, then also open my documents folder
You: TOOL: create_file(python code, open in vscode)
TOOL: open_folder(C:\\Users\\KARAN\\Documents)

User: write html code for a landing page, save it as KD.html in E:\Projects
You: TOOL: create_file(html code for a landing page, save it as KD.html in E:\\Projects)

You will be given "Known facts about the user" - these are permanent, reliable facts (name, 
preferences, etc.) that you should ALWAYS remember and use correctly, no matter how far back 
they were mentioned. Never contradict or forget these facts.

You may also be given "Relevant memories" from past conversations for additional context.

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


# =============================================================================
# PERMISSION SYSTEM
# =============================================================================

def create_permission_request(steps):
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


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.post("/chat")
def chat(request: ChatRequest):
    save_message("user", request.message)
    detect_and_save_facts(request.message)

    play_match = re.search(r"play (.+?) on youtube", request.message, re.IGNORECASE)
    if play_match:
        song_name = play_match.group(1)
        return create_permission_request([("play_youtube", song_name)])

    cursor.execute("SELECT role, content FROM history ORDER BY id DESC LIMIT 6")
    recent = cursor.fetchall()
    recent.reverse()

    relevant = find_relevant_memories(request.message, limit=5)
    memory_context = ""

    facts = get_all_facts()
    if facts:
        memory_context += "Known facts about the user (ALWAYS remember these, never forget):\n"
        for key, value in facts:
            memory_context += f"- {key.replace('_', ' ')}: {value}\n"

    if relevant:
        memory_context += "\nRelevant memories from past conversations:\n"
        for score, role, content in relevant:
            memory_context += f"- {role}: {content}\n"

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + memory_context}]
    for role, content in recent:
        messages.append({"role": "user" if role == "user" else "assistant", "content": content})

    ai_reply = ask_ollama_chat(messages)

    # THE CHAINING FIX: repeat this check up to MAX_TOOL_ROUNDS times, so
    # if the AI wants to use ANOTHER tool after seeing the first tool's
    # results (e.g. searching again with better keywords), it actually
    # gets to run - instead of that request just leaking out as raw,
    # un-executed "TOOL: ..." text like you saw before.
    for round_number in range(MAX_TOOL_ROUNDS):
        tool_matches = re.findall(r"TOOLS?:\s*(\w+)\((.*)\)", ai_reply)

        if not tool_matches:
            # No tool calls this round - this is a normal, final reply
            break

        computer_steps = []
        tool_results = []

        for tool_name, tool_arg in tool_matches:
            if tool_name in COMPUTER_CONTROL_TOOLS:
                computer_steps.append((tool_name, tool_arg))
            elif tool_name == "get_time":
                tool_results.append(get_time(tool_arg.strip() if tool_arg.strip() else None))
            elif tool_name == "calculate":
                tool_results.append(calculate(tool_arg))
            elif tool_name == "search_web":
                tool_results.append(search_web(tool_arg))

        if computer_steps:
            # Computer actions ALWAYS need your permission, no matter which
            # round of the loop we're on - stop immediately and ask
            return create_permission_request(computer_steps)

        if tool_results:
            messages.append({"role": "assistant", "content": ai_reply})
            messages.append({"role": "user", "content": f"Tool results: {'; '.join(tool_results)}. Now reply to me naturally using these results."})
            ai_reply = ask_ollama_chat(messages)
        else:
            # Tool calls were found but didn't match any known tool name -
            # stop here rather than looping forever on something we can't handle
            break

    # SAFETY NET: if we somehow hit the round limit and there's still a raw
    # "TOOL: ..." line left in the text, strip it out so you never see
    # unexecuted tool instructions in the chat
    cleaned_reply = re.sub(r"TOOLS?:\s*\w+\(.*?\)\s*", "", ai_reply).strip()
    if cleaned_reply:
        ai_reply = cleaned_reply
    else:
        ai_reply = "I tried a few different approaches but couldn't get a clean final answer - could you try rephrasing your question?"

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

    if remaining_steps:
        next_request = create_permission_request(remaining_steps)
        next_request["reply"] = f"{tool_result}\n\nNext: {next_request['reply']}"
        return next_request

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