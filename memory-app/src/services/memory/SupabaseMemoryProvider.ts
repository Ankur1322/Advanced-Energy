import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database, MemoryRecord } from "../../types/database";
import type { MemoryProvider } from "./types";

export class SupabaseMemoryProvider implements MemoryProvider {
  constructor(private readonly client: SupabaseClient<Database>, private readonly model: { embed(text: string): Promise<number[]> }) {}

  async search(query: string, userId: string, options: { limit?: number; conversationId?: string } = {}) {
    const embedding = await this.model.embed(query);
    const { data, error } = await this.client.rpc("match_memories", {
      query_embedding: embedding,
      match_user_id: userId,
      match_count: options.limit ?? 8,
      match_conversation_id: options.conversationId ?? null,
    } as never);
    if (error) throw new Error(`Memory search failed: ${error.message}`);
    return (data ?? []) as MemoryRecord[];
  }

  async upsert(input: { userId: string; conversationId?: string; content: string; importance: number; metadata: Record<string, unknown> }) {
    const { data, error } = await this.client.functions.invoke("memory-store", { body: { ...input, importance: Math.max(0, Math.min(1, input.importance)) } });
    if (error) throw new Error(`Memory write failed: ${error.message}`);
    return data as MemoryRecord;
  }

  async deleteByConversation(conversationId: string) {
    const { error } = await this.client.functions.invoke("memory-delete", { body: { conversationId } });
    if (error) throw new Error(`Memory deletion failed: ${error.message}`);
  }
}