"use client";
import { useState, useRef, useEffect } from "react";

type Message = {
  role: "user" | "ai";
  text: string;
  image?: string;
  actionId?: string;
  needsApproval?: boolean;
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInput(transcript);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  function startListening() {
    if (recognitionRef.current) {
      setIsListening(true);
      recognitionRef.current.start();
    } else {
      alert("Voice input isn't supported in this browser. Try Chrome.");
    }
  }

  function speakText(text: string) {
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

    // Images still go through the original, non-streaming flow - a full
    // vision-model reply usually arrives in one go anyway.
    if (imageToSend) {
      const res = await fetch("http://127.0.0.1:8000/chat-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText || "What do you see in this image?",
          image_base64: imageToSend,
        }),
      });
      const data = await res.json();
      const aiMessage: Message = { role: "ai", text: data.reply };
      setMessages((prev) => [...prev, aiMessage]);
      speakText(data.reply);
      setLoading(false);
      return;
    }

    // THE STREAMING FIX: text messages now hit /chat-stream and the reply
    // is read progressively, updating the same message bubble as new
    // words arrive - instead of waiting for the whole answer at once.
    const res = await fetch("http://127.0.0.1:8000/chat-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: messageText }),
    });

    if (!res.body) {
      setLoading(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let accumulatedText = "";
    let isPermissionResponse = false;
    let aiMessageIndex = -1;
    let firstChunkReceived = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunkText = decoder.decode(value, { stream: true });
      accumulatedText += chunkText;

      if (!firstChunkReceived) {
        firstChunkReceived = true;
        setLoading(false);
      }

      if (accumulatedText.startsWith("PERMISSION_JSON:")) {
        // This is a permission request, not normal streaming text - wait
        // until the (short) stream fully ends, then parse it as one piece
        isPermissionResponse = true;
        continue;
      }

      if (aiMessageIndex === -1) {
        // First real chunk of text - create a new AI message bubble
        setMessages((prev) => {
          aiMessageIndex = prev.length;
          return [...prev, { role: "ai", text: accumulatedText }];
        });
      } else {
        // Keep updating the SAME bubble as more words stream in
        setMessages((prev) =>
          prev.map((msg, i) =>
            i === aiMessageIndex ? { ...msg, text: accumulatedText } : msg
          )
        );
      }
    }

    if (isPermissionResponse) {
      const jsonText = accumulatedText.replace("PERMISSION_JSON:", "");
      const data = JSON.parse(jsonText);
      const aiMessage: Message = {
        role: "ai",
        text: data.reply,
        actionId: data.action_id,
        needsApproval: data.needs_permission === true,
      };
      setMessages((prev) => [...prev, aiMessage]);
    } else {
      speakText(accumulatedText);
    }

    setLoading(false);
  }

  async function respondToApproval(actionId: string, approved: boolean, messageIndex: number) {
    setLoading(true);

    const res = await fetch("http://127.0.0.1:8000/approve-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, approved }),
    });

    const data = await res.json();

    setMessages((prev) =>
      prev.map((msg, i) => (i === messageIndex ? { ...msg, needsApproval: false } : msg))
    );

    const resultMessage: Message = {
      role: "ai",
      text: data.reply,
      actionId: data.action_id,
      needsApproval: data.needs_permission === true,
    };
    setMessages((prev) => [...prev, resultMessage]);

    if (!data.needs_permission) {
      speakText(data.reply);
    }

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
              className={`max-w-[70%] px-4 py-2 rounded-2xl whitespace-pre-wrap ${
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

              {msg.needsApproval && msg.actionId && (
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => respondToApproval(msg.actionId!, true, index)}
                    className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-green-700"
                  >
                    ✅ Approve
                  </button>
                  <button
                    onClick={() => respondToApproval(msg.actionId!, false, index)}
                    className="bg-red-500 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-red-600"
                  >
                    ❌ Deny
                  </button>
                </div>
              )}
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