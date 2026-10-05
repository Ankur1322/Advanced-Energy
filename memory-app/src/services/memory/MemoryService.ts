import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database, Conversation, Message } from "../../types/database";
import { SupabaseMemoryProvider } from "./SupabaseMemoryProvider";
import { SupabaseModelClient } from "./SupabaseModelClient";
import type { ChatTurn, MemoryContext, MemoryModelClient, MemoryProvider } from "./types";

const RECENT_MESSAGE_LIMIT = 16;
const SUMMARY_INTERVAL = 20;

export class MemoryService {
  readonly provider: MemoryProvider;
  private readonly model: MemoryModelClient;

  constructor(private readonly client: SupabaseClient<Database>, provider?: MemoryProvider, model?: MemoryModelClient) {
    this.model = model ?? new SupabaseModelClient(client);
    this.provider = provider ?? new SupabaseMemoryProvider(client, this.model);
  }

  async createConversation(userId: string, title = "New conversation") {
    const { data, error } = await this.client.from("conversations").insert({ user_id: userId, title } as never).select().single();
    if (error) throw new Error(`Conversation creation failed: ${error.message}`);
    return data as Conversation;
  }

  async addMessage(conversationId: string, role: Message["role"], content: string, tokenCount = 0) {
    const { data, error } = await this.client.from("messages").insert({ conversation_id: conversationId, role, content, token_count: tokenCount } as never).select().single();
    if (error) throw new Error(`Message creation failed: ${error.message}`);
    return data as Message;
  }

  async getConversationHistory(conversationId: string, limit = 100) {
    const { data, error } = await this.client.from("messages").select("*").eq("conversation_id", conversationId).order("created_at", { ascending: true }).limit(limit);
    if (error) throw new Error(`Conversation history failed: ${error.message}`);
    return (data ?? []) as Message[];
  }

  async retrieveRelevantMemories(query: string, userId: string, limit = 8, conversationId?: string) {
    return this.provider.search(query, userId, { limit: Math.min(Math.max(limit, 1), 8), conversationId });
  }

  async extractAndStoreMemories(userMessage: string, assistantMessage: string, userId: string, conversationId: string) {
    const extraction = await this.model.extract({ userMessage, assistantMessage });
    if (!extraction.should_store || extraction.memories.length === 0) return [];
    return Promise.all(extraction.memories.filter((memory) => memory.importance >= 0.55).map((memory) => this.provider.upsert({
      userId,
      conversationId,
      content: memory.content,
      importance: memory.importance,
      metadata: { ...memory.metadata, type: memory.type, source: "turn-extraction" },
    })));
  }

  async updateConversationSummary(conversationId: string, force = false) {
    const { data: conversationData, error: conversationError } = await this.client.from("conversations").select("*").eq("id", conversationId).single();
    if (conversationError) throw new Error(`Conversation lookup failed: ${conversationError.message}`);
    const conversation = conversationData as Conversation;
    const messages = await this.getConversationHistory(conversationId, 200);
    if (!force && messages.length - conversation.summarized_message_count < SUMMARY_INTERVAL) return conversation.summary;
    const summary = await this.model.summarize({ conversation, messages });
    const { error } = await this.client.from("conversations").update({ summary, summarized_message_count: messages.length } as never).eq("id", conversationId);
    if (error) throw new Error(`Summary update failed: ${error.message}`);
    return summary;
  }

  async buildMemoryContext(query: string, userId: string, conversationId: string): Promise<MemoryContext> {
    const [{ data: conversationData, error }, recentMessages, memories] = await Promise.all([
      this.client.from("conversations").select("*").eq("id", conversationId).single(),
      this.getConversationHistory(conversationId, RECENT_MESSAGE_LIMIT),
      this.retrieveRelevantMemories(query, userId, 8, conversationId),
    ]);
    if (error) throw new Error(`Memory context lookup failed: ${error.message}`);
    return { memories, recentMessages, summary: (conversationData as Conversation).summary };
  }

  async processTurn(turn: ChatTurn, userId: string, conversationId: string) {
    return this.extractAndStoreMemories(turn.role === "user" ? turn.content : "", turn.role === "assistant" ? turn.content : "", userId, conversationId);
  }

  async deleteConversation(conversationId: string) {
    await this.provider.deleteByConversation(conversationId);
    const { error } = await this.client.from("conversations").delete().eq("id", conversationId);
    if (error) throw new Error(`Conversation deletion failed: ${error.message}`);
  }
}