# AI Agent Assistant

A personal AI assistant that I built during my semester break instead of doing nothing. It runs completely on my own PC, remembers things about me across conversations, and can actually *do* things — not just chat.

## Why I built this

I'm currently doing my MSc in Computer Science (Advanced Practice) in the UK, after finishing my Bachelor's in India. During my holidays I wanted to actually build something real instead of just watching tutorials, so I started this as a small chatbot and kept adding features to it over a few sessions until it turned into something genuinely useful.

Everything runs locally using free, open-source AI models through Ollama — no API keys, no monthly costs, no sending my data to a third party.

## What it can actually do

- **Chat normally**, with both short-term memory (recent conversation) and long-term memory (it can search back through *everything* you've ever told it by meaning, not just keywords)
- **Remembers facts about you** permanently — your name, favourite language, even lets you rename the assistant itself
- **Understands images** you send it (describes what's in a photo, reads screenshots)
- **Reads documents** — PDF, Word, and text files — and answers questions about their actual content
- **Real-time weather and time**, anywhere in the world, using proper APIs instead of guessing from search results
- **Sets reminders** in plain English ("remind me at 5pm to call mom") with real browser notifications when they're due
- **Controls your PC**, but only with your permission — opens apps, websites, plays YouTube videos, writes and saves code files — every single action needs an Approve/Deny click first
- **Sends real emails** — you describe what you want to say, the AI writes a proper email, shows it to you, and only sends it once you approve. Has a daily limit built in so nothing can accidentally spam anyone.
- **Learns which actions to trust** — approve something like "open Chrome" three times and it stops asking every time, while riskier things (sending files, emails) always ask
- **Voice input and output** using the browser's built-in speech features
- **Streams replies** word-by-word instead of making you wait for the whole answer
- **Password protected**, and works from your phone too if you're on the same WiFi

## Tech stack

- **Backend:** Python + FastAPI
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **AI models (all local, via Ollama):**
  - `llama3.1` — main chat and reasoning
  - `llava` — image understanding
  - `nomic-embed-text` — turns messages into "meaning fingerprints" for smart memory search
- **Database:** SQLite

## Honest limitations

- The local AI model sometimes misroutes tool calls when a request is oddly phrased or combines too many things at once — it works best with clear, single instructions.
- `llava` isn't perfect at reading small text in screenshots. I tried upgrading to `llama3.2-vision` for better accuracy but hit a genuine bug in Ollama itself (not something I could fix on my end), so I reverted back to `llava`, which is stable.
- This was built and tested on Windows, running on my own machine — it's a personal project, not a production deployment.

## Running it yourself

You'll need [Ollama](https://ollama.com) installed, plus Python and Node.js.

```bash
# pull the models
ollama pull llama3.1
ollama pull llava
ollama pull nomic-embed-text

# backend
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload

# frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

Then open `localhost:3000`. You'll also need a `.env` file in `backend/` with your own password and (optionally) email credentials if you want email sending to work — see the code comments for the exact variable names.

## What I actually learned building this

This was my first time building something end-to-end with a real permission/approval system, working with local LLMs instead of a hosted API, and dealing with genuinely tricky bugs — like a database concurrency issue that caused random crashes under load, and a browser security restriction that silently blocked the whole app on mobile. Debugging those taught me more than most of my coursework has so far.
