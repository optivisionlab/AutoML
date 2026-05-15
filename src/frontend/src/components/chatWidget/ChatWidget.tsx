"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageCircle,
  X,
  Trash2,
  ChevronDown,
  Send,
  Zap,
  Paperclip,
  FileText,
} from "lucide-react";
import {
  sendChatMessage,
  sendChatWithFile,
  clearConversation,
  checkHAgentHealth,
  getConversations,
  getConversationHistory,
  type ChatResponse,
} from "@/api/chatClient";
import { useSession } from "next-auth/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./ChatWidget.module.css";

// ─── Types ──────────────────────────────────────────
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  time: string;
  fileName?: string;
}

// ─── Constants ──────────────────────────────────────
const QUICK_ACTIONS = [
  { emoji: "📁", label: "Xem danh sách datasets" },
  { emoji: "🚀", label: "Train model mới" },
  { emoji: "⚡", label: "Kiểm tra trạng thái hệ thống" },
  { emoji: "🧬", label: "Thuật toán nào phù hợp cho phân loại?" },
] as const;

const ACCEPTED_FILE_TYPES = ".csv,.xls,.xlsx";
const MAX_FILE_SIZE_MB = 50;

// ─── Helpers ────────────────────────────────────────
function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function getCurrentTime(): string {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function mapHistoryMessages(rawMessages: any[]): Message[] {
  return (rawMessages || []).map((m: any, index: number) => {
    const parsedTime = m?.timestamp ? new Date(m.timestamp) : null;
    const displayTime =
      parsedTime && !Number.isNaN(parsedTime.getTime())
        ? parsedTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : getCurrentTime();

    return {
      id: `${m?.role || "assistant"}-${m?.timestamp || "no-ts"}-${index}`,
      role: m?.role === "assistant" ? "assistant" : "user",
      content: typeof m?.content === "string" ? m.content : "",
      time: displayTime,
      fileName:
        typeof m?.content === "string" && m.content.startsWith("Upload file")
          ? "Tệp tin"
          : undefined,
    };
  });
}

function extractErrorMessage(error: any): string {
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string" && detail.length > 0) {
    if (
      detail.includes("Thiếu header Authorization") ||
      detail.includes("Not authenticated")
    ) {
      return "Bạn cần đăng nhập để nhắn tin với trợ lý AI.";
    }
    if (detail.includes("Token đã hết hạn")) {
      return "Phiên đăng nhập đã hết hạn. Vui lòng tải lại trang và đăng nhập lại.";
    }
    if (
      detail.includes("Loại token không hợp lệ") ||
      detail.includes("Token không hợp lệ") ||
      detail.includes("Invalid token") ||
      detail.includes("User not found")
    ) {
      return "Lỗi xác thực người dùng. Vui lòng đăng nhập lại.";
    }
    return detail;
  }

  if (status === 401 || status === 403) {
    return "Bạn cần đăng nhập để sử dụng HAgent.";
  }
  if (status === 502 || status === 503 || status === 504) {
    return "Không kết nối được tới HAgent Bridge. Vui lòng kiểm tra dịch vụ backend.";
  }

  return "Không thể kết nối đến server. Vui lòng kiểm tra kết nối mạng và thử lại.";
}

// ─── Component ──────────────────────────────────────
export default function ChatWidget() {
  const [mounted, setMounted] = useState(false);
  const { data: session } = useSession();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showBadge, setShowBadge] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [hagentStatus, setHagentStatus] = useState<{
    bridgeReachable: boolean;
    gatewayConnected: boolean;
    hautomlConnected: boolean;
  } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Show notification badge after 3 seconds
  useEffect(() => {
    setMounted(true);
    const timer = setTimeout(() => {
      if (!isOpen) setShowBadge(true);
    }, 3000);
    return () => clearTimeout(timer);
  }, [isOpen]);

  // Kiểm tra trạng thái HAgent khi mở chat và thử tải lại hội thoại cũ
  useEffect(() => {
    if (isOpen && hagentStatus === null) {
      checkHAgentHealth()
        .then((health) =>
          setHagentStatus({
            bridgeReachable: true,
            gatewayConnected: health.connected,
            hautomlConnected: health.hautoml_connected,
          })
        )
        .catch(() =>
          setHagentStatus({
            bridgeReachable: false,
            gatewayConnected: false,
            hautomlConnected: false,
          })
        );
    }
  }, [isOpen, hagentStatus]);

  // Tải lịch sử cuộc hội thoại gần nhất khi mở chat
  useEffect(() => {
    if (isOpen && !conversationId && hagentStatus !== null) {
      const loadHistory = async () => {
        try {
          const token = (session?.user as any)?.access_token;
          const list = await getConversations(token);
          if (list?.conversations?.length > 0) {
            const latestId = list.conversations[0].conversation_id;
            const historyData = await getConversationHistory(latestId, token);
            if (historyData && historyData.messages?.length > 0) {
              setConversationId(historyData.conversation_id);
              setMessages(mapHistoryMessages(historyData.messages));
            }
          }
        } catch {
          console.log("Không tìm thấy hội thoại cũ hoặc không tải được");
        }
      };
      // Chỉ tải khi danh sách tin nhắn hiện tại đang trống
      if (messages.length === 0) {
         loadHistory();
      }
    }
  }, [isOpen, conversationId, hagentStatus, messages.length, session]);

  // Đồng bộ tin nhắn mới từ server theo chu kỳ để hiển thị thông báo hậu huấn luyện.
  useEffect(() => {
    if (!isOpen || !conversationId) return;

    let cancelled = false;

    const syncMessages = async () => {
      try {
        const token = (session?.user as any)?.access_token;
        const historyData = await getConversationHistory(conversationId, token);

        if (cancelled || !historyData?.messages) return;

        const nextMessages = mapHistoryMessages(historyData.messages);

        setMessages((prev) => {
          if (nextMessages.length === 0) return prev;

          const prevLast = prev[prev.length - 1];
          const nextLast = nextMessages[nextMessages.length - 1];

          const unchanged =
            prev.length === nextMessages.length &&
            prevLast?.role === nextLast?.role &&
            prevLast?.content === nextLast?.content &&
            prevLast?.time === nextLast?.time;

          return unchanged ? prev : nextMessages;
        });
      } catch {
        // Ignore polling errors to avoid disrupting chat UX.
      }
    };

    void syncMessages();
    const intervalId = window.setInterval(syncMessages, 8000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isOpen, conversationId, session]);

  // Handle textarea auto-resize
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  // Auto-scroll to bottom when new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => inputRef.current?.focus(), 300);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  const toggleChat = useCallback(() => {
    setIsOpen((prev) => {
      if (!prev) setShowBadge(false);
      return !prev;
    });
  }, []);

  // File selection handler
  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        alert(`File quá lớn. Tối đa ${MAX_FILE_SIZE_MB}MB.`);
        return;
      }

      setSelectedFile(file);
      if (!input.trim()) {
        setInput(`Upload file ${file.name} vào hệ thống`);
      }
    },
    [input]
  );

  const clearFile = useCallback(() => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const dispatchMessage = useCallback(
    async (text: string, fileToSend: File | null) => {
      const trimmed = text.trim();
      if ((!trimmed && !fileToSend) || isLoading) return;

      const userMsg: Message = {
        id: generateId(),
        role: "user",
        content: trimmed || `📎 ${fileToSend?.name}`,
        time: getCurrentTime(),
        fileName: fileToSend?.name,
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setSuggestions([]);

      try {
        const token = (session?.user as any)?.access_token;
        const response: ChatResponse = fileToSend
          ? await sendChatWithFile(trimmed, fileToSend, conversationId, token)
          : await sendChatMessage(
              { message: trimmed, conversation_id: conversationId },
              token,
            );

        setConversationId(response.conversation_id);

        const botMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: response.message,
          time: getCurrentTime(),
        };
        setMessages((prev) => [...prev, botMsg]);

        if (response.suggestions?.length) {
          setSuggestions(response.suggestions);
        }
      } catch (error: any) {
        const errorMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: `❌ ${extractErrorMessage(error)}`,
          time: getCurrentTime(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, conversationId, session],
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if ((!text && !selectedFile) || isLoading) return;

    const fileToSend = selectedFile;
    setInput("");
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";

    await dispatchMessage(text, fileToSend);
  }, [input, selectedFile, isLoading, dispatchMessage]);

  const handleQuickSend = useCallback(
    (text: string) => {
      void dispatchMessage(text, null);
    },
    [dispatchMessage],
  );

  const handleClear = useCallback(async () => {
    if (conversationId) {
      try {
        const token = (session as any)?.user?.access_token;
        await clearConversation(conversationId, token);
      } catch (err) {
        console.warn("[ChatWidget] clearConversation failed:", err);
      }
    }
    setMessages([]);
    setSuggestions([]);
    setConversationId(null);
    setSelectedFile(null);
    setHagentStatus(null);
  }, [conversationId, session]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  if (!mounted) return null;

  const showWelcome = messages.length === 0;

  return (
    <>
      {/* ── Floating Action Button ── */}
      <button
        className={`${styles.fab} ${isOpen ? styles.fabOpen : ""}`}
        onClick={toggleChat}
        aria-label={isOpen ? "Đóng chat" : "Mở chat assistant"}
      >
        {showBadge && !isOpen && <span className={styles.badge}>1</span>}
        {isOpen ? <X size={22} /> : <MessageCircle size={26} />}
      </button>

      {/* ── Chat Window ── */}
      <div className={`${styles.window} ${isOpen ? styles.windowVisible : ""}`}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerAvatar}>
            <Zap size={20} />
          </div>
          <div className={styles.headerInfo}>
            <div className={styles.headerTitle}>HAgent</div>
            <div className={styles.headerStatus}>
              <span
                className={styles.statusDot}
                style={{
                  background:
                    hagentStatus === null
                      ? "#888"
                      : hagentStatus.bridgeReachable && hagentStatus.gatewayConnected
                        ? "#00d26a"
                        : hagentStatus.bridgeReachable
                          ? "#f59e0b"
                          : "#ef4444",
                }}
              />
              <span>
                {hagentStatus === null
                  ? "Checking..."
                  : hagentStatus.bridgeReachable && hagentStatus.gatewayConnected
                    ? "HAgent Connected"
                    : hagentStatus.bridgeReachable
                      ? "Bridge Ready · Gateway Connecting..."
                      : "Disconnected"}
              </span>
            </div>
          </div>
          <div className={styles.headerActions}>
            <button
              className={styles.headerBtn}
              onClick={handleClear}
              title="Xóa lịch sử"
            >
              <Trash2 size={16} />
            </button>
            <button
              className={styles.headerBtn}
              onClick={toggleChat}
              title="Thu nhỏ"
            >
              <ChevronDown size={16} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className={styles.messages}>
          {showWelcome && (
            <div className={styles.welcome}>
              <div className={styles.welcomeIcon}>
                <Zap size={28} />
              </div>
              <h3 className={styles.welcomeTitle}>Xin chào! 👋</h3>
              <p className={styles.welcomeDesc}>
                Tôi là trợ lý AI của HAutoML — powered by{" "}
                <strong>HAgent</strong>. Tôi có thể quản lý datasets, train
                models, chạy predictions, và giám sát hệ thống cho bạn.
              </p>
              <div className={styles.welcomeActions}>
                {QUICK_ACTIONS.map((action) => (
                  <button
                    key={action.label}
                    className={styles.welcomeBtn}
                    onClick={() => handleQuickSend(action.label)}
                  >
                    <span>{action.emoji}</span> {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`${styles.message} ${
                msg.role === "user" ? styles.messageUser : styles.messageBot
              }`}
            >
              <div className={styles.msgAvatar}>
                {msg.role === "assistant" ? "AI" : "U"}
              </div>
              <div>
                {msg.fileName && (
                  <div className={styles.fileChip}>
                    <FileText size={14} />
                    <span>{msg.fileName}</span>
                  </div>
                )}
                <div className={`${styles.msgBubble} ${styles.markdownBody}`}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
                <div className={styles.msgTime}>{msg.time}</div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className={styles.typing}>
              <div className={styles.msgAvatar}>AI</div>
              <div className={styles.typingDots}>
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion chips */}
        {suggestions.length > 0 && (
          <div className={styles.suggestions}>
            {suggestions.map((s) => (
              <button
                key={s}
                className={styles.chip}
                onClick={() => handleQuickSend(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* File preview bar */}
        {selectedFile && (
          <div className={styles.filePreview}>
            <FileText size={16} />
            <span className={styles.filePreviewName}>{selectedFile.name}</span>
            <span className={styles.filePreviewSize}>
              ({formatFileSize(selectedFile.size)})
            </span>
            <button
              className={styles.filePreviewClose}
              onClick={clearFile}
              title="Xóa file"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Input Area */}
        <div className={styles.inputArea}>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            onChange={handleFileSelect}
            style={{ display: "none" }}
            id="chat-file-input"
          />
          <button
            className={styles.attachBtn}
            onClick={() => fileInputRef.current?.click()}
            title="Đính kèm file (CSV, Excel)"
            disabled={isLoading}
          >
            <Paperclip size={18} />
          </button>
          <textarea
            ref={inputRef}
            className={styles.input}
            placeholder="Hỏi tôi bất cứ điều gì..."
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={(!input.trim() && !selectedFile) || isLoading}
            aria-label="Gửi tin nhắn"
          >
            <Send size={18} />
          </button>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          🔬 Powered by{" "}
          <a
            href="https://optivisionlab.fit-haui.edu.vn/"
            target="_blank"
            rel="noopener noreferrer"
          >
            OptivisionLab
          </a>{" "}
          •{" "}
          <a
            href=""
            target="_blank"
            rel="noopener noreferrer"
          >
            HAgent
          </a>
        </div>
      </div>
    </>
  );
}
