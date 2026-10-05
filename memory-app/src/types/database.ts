export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type MessageRole = "system" | "user" | "assistant" | "tool";

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  summary: string | null;
  pinned: boolean;
  message_count: number;
  summarized_message_count: number;
  created_at: string;
  updated_at: string;
  preview?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  token_count: number;
  created_at: string;
}

export interface MemoryRecord {
  id: string;
  user_id: string;
  conversation_id: string | null;
  content: string;
  importance: number;
  metadata: Record<string, Json>;
  created_at: string;
  similarity?: number;
}

export interface Database {
  public: {
    Tables: {
      conversations: { Row: Conversation; Insert: Partial<Conversation> & Pick<Conversation, "user_id">; Update: Partial<Conversation>; Relationships: [] };
      messages: { Row: Message; Insert: Omit<Message, "id" | "created_at">; Update: Partial<Message>; Relationships: [] };
      memories: { Row: MemoryRecord; Insert: Omit<MemoryRecord, "id" | "created_at"> & { embedding: number[] }; Update: Partial<MemoryRecord>; Relationships: [] };
    };
    Views: Record<string, never>;
    Functions: {
      match_memories: {
        Args: { query_embedding: number[]; match_user_id: string; match_count?: number; match_conversation_id?: string | null };
        Returns: MemoryRecord[];
      };
    };
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
}