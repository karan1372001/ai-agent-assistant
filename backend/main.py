from fastapi import FastAPI
# FastAPI = the tool that lets us build our backend server

from fastapi.middleware.cors import CORSMiddleware
# This lets our webpage (frontend) talk to our backend safely

from pydantic import BaseModel
# This helps us define what kind of data we expect to receive

import requests
# This lets our backend send requests to Ollama (our local AI)

app = FastAPI()
# Create our actual backend app

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Allow requests from any website (fine for now, while testing)
    allow_methods=["*"],   # Allow all types of requests (GET, POST, etc.)
    allow_headers=["*"],   # Allow all header types
)
# Without this, your webpage wouldn't be allowed to talk to your backend

class ChatRequest(BaseModel):
    message: str
# This defines what data we expect when someone sends a chat message
# We expect one thing: a "message" that is text

@app.get("/")
def read_root():
    return {"status": "Backend is running"}
# This is a simple test route - if you visit the homepage, it confirms the server is alive

@app.post("/chat")
def chat(request: ChatRequest):
    # This function runs whenever someone sends a message to /chat

    response = requests.post(
        "http://localhost:11434/api/generate",
        # This is Ollama's local address - our AI model running on your PC

        json={
            "model": "llama3.1",       # Which AI model to use
            "prompt": request.message, # The message the user typed
            "stream": False            # Get the full answer at once (not word-by-word)
        }
    )

    result = response.json()
    # Convert Ollama's reply into usable data

    return {"reply": result["response"]}
    # Send the AI's reply back to the webpage