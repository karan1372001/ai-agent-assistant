"use client";
// Tells Next.js this page runs in the browser (needed since we use buttons, typing, etc.)

import { useState, useRef, useEffect } from "react";
// useState = lets us store values that can change (like your typed message)
// useRef = lets us remember something without refreshing the page (used for auto-scroll)
// useEffect = runs code automatically whenever something changes

// This defines what one chat bubble looks like (shown in the main chat window)
type Message = {
  role: "user" | "ai";
  text: string;
};

// This defines what one history entry looks like (pulled from the database)
type HistoryItem = {
  role: string;
  content: string;
  timestamp: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  // messages = the current chat conversation shown on screen

  const [input, setInput] = useState("");
  // input = whatever you're currently typing in the box

  const [loading, setLoading] = useState(false);
  // loading = true while we're waiting for the AI's reply (shows "Thinking...")

  const [showHistory, setShowHistory] = useState(false);
  // showHistory = true when the History panel should be visible on screen

  const [history, setHistory] = useState<HistoryItem[]>([]);
  // history = all past messages pulled from the database, with timestamps

  const bottomRef = useRef<HTMLDivElement>(null);
  // this is an invisible marker at the bottom of the chat, used to auto-scroll down

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  // every time "messages" changes (new message added), scroll down automatically

  async function sendMessage() {
    if (!input.trim()) return;
    // if the box is empty (or just spaces), don't send anything

    const userMessage: Message = { role: "user", text: input };
    setMessages((prev) => [...prev, userMessage]);
    // add your new message to the chat immediately, so you see it right away

    setInput("");
    // clear the typing box after sending

    setLoading(true);
    // show "Thinking..." while we wait for the AI

    const res = await fetch("http://127.0.0.1:8000/chat", {
      // send your message to our Python backend
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMessage.text }),
    });

    const data = await res.json();
    // wait for the backend's reply and convert it into usable data

    const aiMessage: Message = { role: "ai", text: data.reply };
    setMessages((prev) => [...prev, aiMessage]);
    // add the AI's reply to the chat window

    setLoading(false);
    // stop showing "Thinking..."
  }

  async function openHistory() {
    // this runs when you click the "History" button

    const res = await fetch("http://127.0.0.1:8000/history");
    // ask the backend for ALL past messages ever saved

    const data = await res.json();
    setHistory(data.history);
    // store that full list

    setShowHistory(true);
    // show the history panel on screen
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
  // lets you press Enter to send a message, like a normal chat app
  // (Shift+Enter still lets you add a new line instead of sending)

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* This is the whole page layout, full height, light gray background */}

      {/* ---------- Header bar at the top ---------- */}
      <div className="bg-white shadow p-4 flex justify-between items-center">
        <h1 className="text-xl font-semibold">Karan's AI Assistant</h1>
        <button
          onClick={openHistory}
          className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1.5 rounded-lg"
        >
          History
        </button>
      </div>

      {/* ---------- History panel (only shows when showHistory is true) ---------- */}
      {showHistory && (
        <div className="absolute inset-0 bg-white z-10 flex flex-col">
          {/* This covers the whole screen like a popup page */}

          <div className="p-4 bg-white shadow flex justify-between items-center">
            <h2 className="text-lg font-semibold">Chat History</h2>
            <button
              onClick={() => setShowHistory(false)}
              className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1.5 rounded-lg"
            >
              Close
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {history.length === 0 && <p className="text-gray-500">No history yet.</p>}
            {/* If there's no history at all, show a simple message instead */}

            {history.map((item, index) => (
              // Loop through every single saved message and display it

              <div key={index} className="border-b pb-2 flex justify-between items-start gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">{item.role}</div>
                  {/* Shows "user" or "assistant" as a small label */}

                  <div>{item.content}</div>
                  {/* The actual message text */}
                </div>

                <div className="text-xs text-gray-400 whitespace-nowrap">
                  {item.timestamp}
                  {/* The exact date and time, shown on the right side */}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------- Main chat conversation area ---------- */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, index) => (
          // Loop through the current conversation and show each bubble

          <div
            key={index}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            // Your messages align right, AI messages align left
          >
            <div
              className={`max-w-[70%] px-4 py-2 rounded-2xl ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-none"
                  : "bg-white text-gray-800 rounded-bl-none shadow"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white text-gray-500 px-4 py-2 rounded-2xl shadow">
              Thinking...
            </div>
          </div>
        )}
        {/* Shows a "Thinking..." bubble while waiting for the AI */}

        <div ref={bottomRef} />
        {/* Invisible marker used to auto-scroll to the bottom */}
      </div>

      {/* ---------- Input area at the bottom ---------- */}
      <div className="p-4 bg-white border-t flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          className="flex-1 resize-none border rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={1}
        />
        <button
          onClick={sendMessage}
          className="bg-blue-600 text-white px-4 py-2 rounded-xl hover:bg-blue-700"
        >
          Send
        </button>
      </div>
    </div>
  );
}