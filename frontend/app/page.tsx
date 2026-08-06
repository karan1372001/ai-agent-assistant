"use client"; 
// This tells Next.js: "this page needs to run in the browser" (because we're using buttons, typing, etc.)

import { useState } from "react"; 
// This lets us store and update values on the page (like the message you type)

export default function Home() {
  // This is the main webpage component - everything inside runs when the page loads

  const [message, setMessage] = useState(""); 
  // "message" = what you're currently typing
  // setMessage = the function we use to update it

  const [reply, setReply] = useState(""); 
  // "reply" = the AI's response, starts empty

  const [loading, setLoading] = useState(false); 
  // "loading" = true while we're waiting for the AI to respond, so we can show "Thinking..."

  async function sendMessage() {
    // This function runs when you click the Send button

    setLoading(true); 
    // Show "Thinking..." while we wait

    const res = await fetch("http://127.0.0.1:8000/chat", {
      // Send your message to your Python backend (the one running on port 8000)
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }), 
      // Package your typed message to send it
    });

    const data = await res.json(); 
    // Wait for the backend's response and convert it to usable data

    setReply(data.reply); 
    // Show the AI's reply on screen

    setLoading(false); 
    // Stop showing "Thinking..."
  }

  return (
    // This is what actually shows up on the webpage (the visible design)

    <div style={{ padding: "40px", maxWidth: "600px", margin: "0 auto" }}>
      
      <h1>My AI Assistant</h1>
      {/* Page title */}

      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)} 
        // Every time you type, update "message" with what you typed
        placeholder="Type your message..."
        style={{ width: "100%", height: "100px", padding: "10px" }}
      />
      {/* This is the box where you type your message */}

      <br />

      <button onClick={sendMessage} style={{ marginTop: "10px", padding: "10px 20px" }}>
        {loading ? "Thinking..." : "Send"}
        {/* Button text changes to "Thinking..." while waiting for AI */}
      </button>

      <div style={{ marginTop: "20px", padding: "10px", background: "#f0f0f0" }}>
        <strong>AI Reply:</strong>
        <p>{reply}</p>
        {/* This is where the AI's answer appears */}
      </div>
    </div>
  );
}