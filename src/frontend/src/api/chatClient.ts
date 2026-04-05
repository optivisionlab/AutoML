import axios from "axios";
import { getSession } from "next-auth/react";

// ─── HAgent Bridge Client ────────────────────────────
// Dùng riêng một axios instance cho HAgent Bridge service (host port 8900).
// Tách biệt hoàn toàn với axiosClient chính (HAutoML backend).

const hagentClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_HAGENT_URL || "http://localhost:8900",
});

// Bỏ interceptor để gửi token trực tiếp qua hàm sendChatMessage

// ─── Types ──────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string | null;
  context?: Record<string, unknown>;
  /** LLM provider: google, openai, anthropic, ollama */
  provider?: string | null;
  /** Tên model cụ thể muốn sử dụng */
  model?: string | null;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
  sources?: string[];
  suggestions?: string[];
}

export interface SuggestionsResponse {
  suggestions: string[];
}

export interface HealthResponse {
  hagent_url: string;
  connected: boolean;
  hautoml_connected: boolean;
  mode: string;
}

// ─── API Functions ──────────────────────────────────────

const CHAT_ENDPOINT = "/api/v1/chat";

export async function sendChatMessage(req: ChatRequest, token?: string): Promise<ChatResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    // Lấy thử từ next-auth nếu không truyền
    const session: any = await getSession();
    if (session?.user?.access_token) {
      headers["Authorization"] = `Bearer ${session.user.access_token}`;
    }
  }

  const { data } = await hagentClient.post<ChatResponse>(`${CHAT_ENDPOINT}/`, req, {
    headers
  });
  return data;
}

/**
 * Gửi tin nhắn kèm file đính kèm.
 * Dùng để upload dataset hoặc dữ liệu inference qua chat widget.
 */
export async function sendChatWithFile(
  message: string,
  file: File,
  conversationId?: string | null,
  token?: string
): Promise<ChatResponse> {
  const formData = new FormData();
  formData.append("message", message || `Upload file ${file.name}`);
  formData.append("file", file);
  if (conversationId) {
    formData.append("conversation_id", conversationId);
  }

  const headers: Record<string, string> = {
    "Content-Type": "multipart/form-data",
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    // Lấy thử từ next-auth nếu không truyền
    const session: any = await getSession();
    if (session?.user?.access_token) {
      headers["Authorization"] = `Bearer ${session.user.access_token}`;
    }
  }

  const { data } = await hagentClient.post<ChatResponse>(
    `${CHAT_ENDPOINT}/upload`,
    formData,
    {
      headers,
      timeout: 120_000, // upload file có thể mất lâu hơn
    }
  );
  return data;
}

export async function getInitialSuggestions(): Promise<SuggestionsResponse> {
  const { data } = await hagentClient.get<SuggestionsResponse>(`${CHAT_ENDPOINT}/suggestions`);
  return data;
}

/**
 * Kiểm tra trạng thái kết nối của HAgent gateway.
 */
export async function checkHAgentHealth(): Promise<HealthResponse> {
  const { data } = await hagentClient.get<HealthResponse>(`${CHAT_ENDPOINT}/health`);
  return data;
}

export async function clearConversation(conversationId: string): Promise<void> {
  await hagentClient.delete(`${CHAT_ENDPOINT}/conversation/${conversationId}`);
}


/**
 * Lấy danh sách các cuộc hội thoại gần đây.
 */
export async function getConversations(token?: string): Promise<any> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    const session: any = await getSession();
    if (session?.user?.access_token) {
      headers["Authorization"] = `Bearer ${session.user.access_token}`;
    }
  }
  const { data } = await hagentClient.get(`${CHAT_ENDPOINT}/conversations`, { headers });
  return data;
}

/**
 * Lấy toàn bộ tin nhắn của một cuộc hội thoại cụ thể.
 */
export async function getConversationHistory(conversationId: string, token?: string): Promise<any> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    const session: any = await getSession();
    if (session?.user?.access_token) {
      headers["Authorization"] = `Bearer ${session.user.access_token}`;
    }
  }
  const { data } = await hagentClient.get(`${CHAT_ENDPOINT}/conversation/${conversationId}`, { headers });
  return data;
}
