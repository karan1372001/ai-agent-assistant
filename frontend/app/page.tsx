"use client";
import { useState, useRef, useEffect } from "react";

type Message = {
  role: "user" | "ai";
  text: string;
  image?: string;
};

type HistoryItem = {
  role: string;
  content: string;
  timestamp: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  // isListening = true while the microphone is actively listening to you

  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  // recognitionRef = holds the browser's built-in speech recognition tool

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    // Set up the browser's speech recognition ONCE when the page loads
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    // Chrome calls it "webkitSpeechRecognition" internally

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false; // stops listening after one sentence
      recognition.interimResults = false; // only gives us the final text, not partial guesses
      recognition.lang = "en-US";

      recognition.onresult = (event: any) => {
        // This runs when the browser finishes understanding what you said
        const transcript = event.results[0][0].transcript;
        setInput(transcript); // put the spoken text into the input box
      };

      recognition.onend = () => {
        setIsListening(false); // turn off the "listening" indicator when done
      };

      recognitionRef.current = recognition;
    }
  }, []);

  function startListening() {
    if (recognitionRef.current) {
      setIsListening(true);
      recognitionRef.current.start(); // begin listening through your microphone
    } else {
      alert("Voice input isn't supported in this browser. Try Chrome.");
    }
  }

  function speakText(text: string) {
    // Makes your browser read the AI's reply out loud
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = (reader.result as string).split(",")[1];
      setSelectedImage(base64String);
    };
    reader.readAsDataURL(file);
  }

  async function sendMessage() {
    if (!input.trim() && !selectedImage) return;

    const userMessage: Message = {
      role: "user",
      text: input || "(sent an image)",
      image: selectedImage || undefined,
    };
    setMessages((prev) => [...prev, userMessage]);

    const messageText = input;
    const imageToSend = selectedImage;

    setInput("");
    setSelectedImage(null);
    setLoading(true);

    let res;

    if (imageToSend) {
      res = await fetch("http://127.0.0.1:8000/chat-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText || "What do you see in this image?",
          image_base64: imageToSend,
        }),
      });
    } else {
      res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText }),
      });
    }

    const data = await res.json();
    const aiMessage: Message = { role: "ai", text: data.reply };
    setMessages((prev) => [...prev, aiMessage]);

    speakText(data.reply);
    // As soon as the AI replies, read it out loud automatically

    setLoading(false);
  }

  async function openHistory() {
    const res = await fetch("http://127.0.0.1:8000/history");
    const data = await res.json();
    setHistory(data.history);
    setShowHistory(true);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      
      <div className="bg-white shadow p-4 flex justify-between items-center">
        <h1 className="text-xl font-semibold">Karan's AI Assistant</h1>
        <button
          onClick={openHistory}
          className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1.5 rounded-lg"
        >
          History
        </button>
      </div>

      {showHistory && (
        <div className="absolute inset-0 bg-white z-10 flex flex-col">
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
            {history.map((item, index) => (
              <div key={index} className="border-b pb-2 flex justify-between items-start gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">{item.role}</div>
                  <div>{item.content}</div>
                </div>
                <div className="text-xs text-gray-400 whitespace-nowrap">
                  {item.timestamp}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[70%] px-4 py-2 rounded-2xl ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-none"
                  : "bg-white text-gray-800 rounded-bl-none shadow"
              }`}
            >
              {msg.image && (
                <img
                  src={`data:image/png;base64,${msg.image}`}
                  alt="attached"
                  className="rounded-lg mb-2 max-w-full max-h-64 object-contain"
                />
              )}
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

        <div ref={bottomRef} />
      </div>

      {selectedImage && (
        <div className="px-4 pt-2 bg-white">
          <div className="relative inline-block">
            <img
              src={`data:image/png;base64,${selectedImage}`}
              alt="preview"
              className="h-20 rounded-lg"
            />
            <button
              onClick={() => setSelectedImage(null)}
              className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 text-xs"
            >
              ×
            </button>
          </div>
        </div>
      )}

      <div className="p-4 bg-white border-t flex gap-2 items-end">
        <input
          type="file"
          accept="image/*"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
        />

        <button
          onClick={handleAttachClick}
          className="bg-gray-200 hover:bg-gray-300 px-3 py-2 rounded-xl text-lg"
          title="Attach image"
        >
          📎
        </button>

        <button
          onClick={startListening}
          className={`px-3 py-2 rounded-xl text-lg ${
            isListening ? "bg-red-500 text-white animate-pulse" : "bg-gray-200 hover:bg-gray-300"
          }`}
          title="Speak your message"
        >
          🎤
        </button>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type or speak a message..."
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