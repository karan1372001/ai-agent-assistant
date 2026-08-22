"use client";
import { useState, useRef, useEffect } from "react";

type Message = {
  role: "user" | "ai";
  text: string;
  image?: string;
  documentName?: string;
  actionId?: string;
  needsApproval?: boolean;
};

type HistoryItem = {
  role: string;
  content: string;
  timestamp: string;
};

type ReminderItem = {
  id: number;
  message: string;
  remind_at: string;
  created_at: string;
  notified: boolean;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showReminders, setShowReminders] = useState(false);
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<{ name: string; base64: string } | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [sessionId, setSessionId] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    setSessionId(crypto.randomUUID());
  }, []);

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

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/reminders/due");
        const data = await res.json();
        if (data.due && data.due.length > 0) {
          for (const reminder of data.due) {
            const text = `⏰ Reminder: ${reminder.message}`;
            setMessages((prev) => [...prev, { role: "ai", text }]);

            if ("Notification" in window && Notification.permission === "granted") {
              new Notification("AI Assistant Reminder", { body: reminder.message });
            }

            speakText(text);
          }
        }
      } catch (e) {
        // Backend might be momentarily unreachable - just skip this check
      }
    }, 20000);

    return () => clearInterval(interval);
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

  // THE DOCUMENT UPLOAD FIX: same idea as image attaching, but for PDF,
  // Word, and text files. Converts the chosen file to base64 so it can
  // be sent to the backend, where the actual text gets extracted.
  function handleDocumentClick() {
    documentInputRef.current?.click();
  }

  function handleDocumentChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowedExtensions = [".pdf", ".docx", ".txt"];
    const lowerName = file.name.toLowerCase();
    if (!allowedExtensions.some((ext) => lowerName.endsWith(ext))) {
      alert("Please choose a .pdf, .docx, or .txt file.");
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = (reader.result as string).split(",")[1];
      setSelectedDocument({ name: file.name, base64: base64String });
    };
    reader.readAsDataURL(file);
  }

  function startNewChat() {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  }

  async function exportHistory() {
    const res = await fetch("http://127.0.0.1:8000/history");
    const data = await res.json();
    const items: HistoryItem[] = data.history;

    if (!items || items.length === 0) {
      alert("There's no chat history to export yet.");
      return;
    }

    let fileContent = "KARAN'S AI ASSISTANT - CHAT HISTORY EXPORT\n";
    fileContent += `Exported on: ${new Date().toLocaleString()}\n`;
    fileContent += `Total messages: ${items.length}\n`;
    fileContent += "=".repeat(50) + "\n\n";

    for (const item of items) {
      const speaker = item.role === "user" ? "You" : "AI Assistant";
      fileContent += `[${item.timestamp}] ${speaker}:\n${item.content}\n\n`;
    }

    const blob = new Blob([fileContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const dateStamp = new Date().toISOString().split("T")[0];
    const link = document.createElement("a");
    link.href = url;
    link.download = `ai-assistant-chat-history-${dateStamp}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  async function openReminders() {
    const res = await fetch("http://127.0.0.1:8000/reminders");
    const data = await res.json();
    setReminders(data.reminders);
    setShowReminders(true);
  }

  async function deleteReminder(id: number) {
    await fetch("http://127.0.0.1:8000/reminders/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    setReminders((prev) => prev.filter((r) => r.id !== id));
  }

  async function sendMessage() {
    if (!input.trim() && !selectedImage && !selectedDocument) return;

    // Document messages are handled separately, non-streamed (same
    // pattern as images) since they go through their own dedicated
    // endpoint that extracts text first.
    if (selectedDocument) {
      const userMessage: Message = {
        role: "user",
        text: input || `What can you tell me about ${selectedDocument.name}?`,
        documentName: selectedDocument.name,
      };
      setMessages((prev) => [...prev, userMessage]);

      const messageText = input;
      const docToSend = selectedDocument;

      setInput("");
      setSelectedDocument(null);
      setLoading(true);

      const res = await fetch("http://127.0.0.1:8000/chat-document", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText || `What can you tell me about ${docToSend.name}?`,
          filename: docToSend.name,
          file_base64: docToSend.base64,
          session_id: sessionId,
        }),
      });
      const data = await res.json();
      const aiMessage: Message = { role: "ai", text: data.reply };
      setMessages((prev) => [...prev, aiMessage]);
      speakText(data.reply);
      setLoading(false);
      return;
    }

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

    if (imageToSend) {
      const res = await fetch("http://127.0.0.1:8000/chat-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText || "What do you see in this image?",
          image_base64: imageToSend,
          session_id: sessionId,
        }),
      });
      const data = await res.json();
      const aiMessage: Message = { role: "ai", text: data.reply };
      setMessages((prev) => [...prev, aiMessage]);
      speakText(data.reply);
      setLoading(false);
      return;
    }

    const res = await fetch("http://127.0.0.1:8000/chat-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: messageText, session_id: sessionId }),
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
        isPermissionResponse = true;
        continue;
      }

      if (aiMessageIndex === -1) {
        setMessages((prev) => {
          aiMessageIndex = prev.length;
          return [...prev, { role: "ai", text: accumulatedText }];
        });
      } else {
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
        <div className="flex gap-2">
          <button
            onClick={startNewChat}
            className="bg-blue-100 hover:bg-blue-200 text-blue-700 text-sm px-3 py-1.5 rounded-lg"
            title="Start a fresh conversation (your memory and facts stay intact)"
          >
            🆕 New Chat
          </button>
          <button
            onClick={openReminders}
            className="bg-yellow-100 hover:bg-yellow-200 text-yellow-800 text-sm px-3 py-1.5 rounded-lg"
          >
            🔔 Reminders
          </button>
          <button
            onClick={openHistory}
            className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1.5 rounded-lg"
          >
            History
          </button>
          <button
            onClick={exportHistory}
            className="bg-green-100 hover:bg-green-200 text-green-700 text-sm px-3 py-1.5 rounded-lg"
            title="Download your full chat history as a text file"
          >
            ⬇️ Export
          </button>
        </div>
      </div>

      {showHistory && (
        <div className="absolute inset-0 bg-white z-10 flex flex-col">
          <div className="p-4 bg-white shadow flex justify-between items-center">
            <h2 className="text-lg font-semibold">Chat History</h2>
            <div className="flex gap-2">
              <button
                onClick={exportHistory}
                className="bg-green-100 hover:bg-green-200 text-green-700 text-sm px-3 py-1.5 rounded-lg"
              >
                ⬇️ Export
              </button>
              <button
                onClick={() => setShowHistory(false)}
                className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1.5 rounded-lg"
              >
                Close
              </button>
            </div>
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

      {showReminders && (
        <div className="absolute inset-0 bg-white z-10 flex flex-col">
          <div className="p-4 bg-white shadow flex justify-between items-center">
            <h2 className="text-lg font-semibold">Reminders</h2>
            <button
              onClick={() => setShowReminders(false)}
              className="bg-gray-200 hover:bg-gray-300 text-sm px-3 py-1.5 rounded-lg"
            >
              Close
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {reminders.length === 0 && (
              <p className="text-gray-500">
                No reminders yet. Try saying "remind me at 5pm to call mom".
              </p>
            )}
            {reminders.map((item) => (
              <div
                key={item.id}
                className={`border rounded-lg p-3 flex justify-between items-start gap-4 ${
                  item.notified ? "bg-gray-50 text-gray-400" : "bg-yellow-50"
                }`}
              >
                <div>
                  <div className="font-medium">{item.message}</div>
                  <div className="text-xs mt-1">
                    {item.notified ? "Already reminded at" : "Will remind at"}: {item.remind_at}
                  </div>
                </div>
                <button
                  onClick={() => deleteReminder(item.id)}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-8">
            Start a new conversation - your saved memory and facts are still here.
          </div>
        )}
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
              {msg.documentName && (
                <div
                  className={`mb-2 flex items-center gap-2 rounded-lg px-2 py-1 text-sm ${
                    msg.role === "user" ? "bg-blue-500/30" : "bg-gray-100"
                  }`}
                >
                  📄 {msg.documentName}
                </div>
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

      {selectedDocument && (
        <div className="px-4 pt-2 bg-white">
          <div className="relative inline-flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2">
            <span className="text-sm">📄 {selectedDocument.name}</span>
            <button
              onClick={() => setSelectedDocument(null)}
              className="text-red-500 hover:text-red-700 text-xs font-bold"
            >
              ✕
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

        <input
          type="file"
          accept=".pdf,.docx,.txt"
          ref={documentInputRef}
          onChange={handleDocumentChange}
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
          onClick={handleDocumentClick}
          className="bg-gray-200 hover:bg-gray-300 px-3 py-2 rounded-xl text-lg"
          title="Attach document (PDF, Word, or text file)"
        >
          📄
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