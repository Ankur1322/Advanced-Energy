import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "../../types/database";
import type { Conversation, Message } from "../../types/database";
import type { MemoryModelClient } from "./types";

export class SupabaseModelClient implements MemoryModelClient {
  constructor(private readonly client: SupabaseClient<Database>) {}

  private async invoke<T>(functionName: string, body: Record<string, unknown>): Promise<T> {
    const { data, error } = await this.client.functions.invoke(functionName, { body });
    if (error) throw new Error(`${functionName} failed: ${error.message}`);
    return data as T;
  }

  extract(turn: { userMessage: string; assistantMessage: string }) {
    return this.invoke<Awaited<ReturnType<MemoryModelClient["extract"]>>>("memory-extract", turn);
  }

  async embed(text: string) {
    const result = await this.invoke<{ embedding: number[] }>("memory-embed", { text });
    if (result.embedding.length !== 1536) throw new Error("Embedding dimension must be 1536");
    return result.embedding;
  }

  async summarize(input: { conversation: Conversation; messages: Message[] }) {
    const result = await this.invoke<{ summary: string }>("memory-summarize", input);
    return result.summary;
  }
}