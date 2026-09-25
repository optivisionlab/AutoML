"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { Bot, RotateCcw, Send, X } from "lucide-react";

const AGENT_API = process.env.NEXT_PUBLIC_AGENT_API || "http://localhost:9500";

interface Message {
  role: "user" | "agent";
  text: string;
  tools?: string[];
}

const SUGGESTIONS = [
  "Tôi có dataset nào?",
  "Dataset của tôi có những cột gì?",
  "Tôi đã train job nào chưa?",
];

export default function AgentChat() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Cuộn xuống tin nhắn mới nhất mỗi khi danh sách đổi.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || sending) return;

    setMessages((prev) => [...prev, { role: "user", text: content }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch(`${AGENT_API}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
          // Agent dùng luôn token của phiên web, không tự đăng nhập lại.
          access_token: session?.user?.access_token ?? null,
        }),
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status} ${detail.slice(0, 200)}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: data.reply, tools: data.tools },
      ]);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          text:
            `Không gọi được agent: ${reason}\n\n` +
            `Kiểm tra service đã chạy chưa:\n` +
            `  cd src/backend && python -m agent.server`,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function reset() {
    if (sessionId) {
      await fetch(`${AGENT_API}/agent/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "reset", session_id: sessionId }),
      }).catch(() => undefined);
    }
    setMessages([]);
    setSessionId(null);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Mở trợ lý HAutoML"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition hover:bg-blue-700"
      >
        <Bot className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex h-[560px] w-[92vw] max-w-[420px] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900">
      <header className="flex items-center justify-between border-b border-gray-200 bg-blue-600 px-4 py-3 text-white dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <span className="font-semibold">Trợ lý HAutoML</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={reset} title="Xoá hội thoại" className="rounded p-1 hover:bg-white/20">
            <RotateCcw className="h-4 w-4" />
          </button>
          <button onClick={() => setOpen(false)} title="Đóng" className="rounded p-1 hover:bg-white/20">
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto bg-gray-50 p-4 dark:bg-gray-800">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {session?.user
                ? "Xin chào! Tôi tra cứu dataset và job huấn luyện giúp bạn."
                : "Bạn chưa đăng nhập. Hãy đăng nhập để tôi truy cập được dữ liệu của bạn."}
            </p>
            {SUGGESTIONS.map((text) => (
              <button
                key={text}
                onClick={() => send(text)}
                className="block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm transition hover:border-blue-400 dark:border-gray-600 dark:bg-gray-700"
              >
                {text}
              </button>
            ))}
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={
                "max-w-[85%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm " +
                (message.role === "user"
                  ? "bg-blue-600 text-white"
                  : "border border-gray-200 bg-white text-gray-800 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100")
              }
            >
              {message.tools && message.tools.length > 0 && (
                <div className="mb-1 flex flex-wrap gap-1">
                  {message.tools.map((tool, i) => (
                    <span
                      key={i}
                      className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-600 dark:bg-gray-600 dark:text-gray-200"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              )}
              {message.text}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-500 dark:border-gray-600 dark:bg-gray-700">
              Đang xử lý…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(input);
        }}
        className="flex gap-2 border-t border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900"
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Hỏi về dataset, job huấn luyện…"
          disabled={sending}
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:opacity-60 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-lg bg-blue-600 px-3 text-white transition hover:bg-blue-700 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
