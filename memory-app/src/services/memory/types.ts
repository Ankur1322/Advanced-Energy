import type { Conversation, MemoryRecord, Message, MessageRole } from "../../types/database";

export interface ChatTurn {
  role: Extract<MessageRole, "user" | "assistant">;
  content: string;
}

export interface MemoryExtraction {
  should_store: boolean;
  memories: Array<{
    content: string;
    importance: number;
    type: "fact" | "preference" | "entity" | "decision";
    metadata?: Record<string, unknown>;
  }>;
}

export interface MemoryContext {
  memories: MemoryRecord[];
  summary: string | null;
  recentMessages: Message[];
}

export interface MemoryProvider {
  search(query: string, userId: string, options?: { limit?: number; conversationId?: string }): Promise<MemoryRecord[]>;
  upsert(input: { userId: string; conversationId?: string; content: string; importance: number; metadata: Record<string, unknown> }): Promise<MemoryRecord>;
  deleteByConversation(conversationId: string): Promise<void>;
}

export interface MemoryModelClient {
  extract(turn: { userMessage: string; assistantMessage: string }): Promise<MemoryExtraction>;
  embed(text: string): Promise<number[]>;
  summarize(input: { conversation: Conversation; messages: Message[] }): Promise<string>;
}