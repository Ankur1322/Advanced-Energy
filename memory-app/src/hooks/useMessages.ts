import { useEffect, useState } from "react";
import type { Message, MessageRole } from "../types/database";
import { supabase } from "../lib/supabase";
import { MemoryService } from "../services/memory/MemoryService";

const memoryService = new MemoryService(supabase);

export function useMessages(conversationId: string | undefined) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(conversationId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!conversationId) { setMessages([]); setIsLoading(false); return; }
    let active = true;
    setIsLoading(true);
    void memoryService.getConversationHistory(conversationId).then((history) => { if (active) setMessages(history); }).catch((loadError: Error) => { if (active) setError(loadError.message); }).finally(() => { if (active) setIsLoading(false); });
    const channel = supabase.channel(`messages:${conversationId}`).on("postgres_changes", { event: "INSERT", schema: "public", table: "messages", filter: `conversation_id=eq.${conversationId}` }, (payload) => {
      if (active) setMessages((current) => current.some((message) => message.id === payload.new.id) ? current : [...current, payload.new as Message]);
    }).subscribe();
    return () => { active = false; void supabase.removeChannel(channel); };
  }, [conversationId]);

  async function add(role: MessageRole, content: string) {
    if (!conversationId) throw new Error("Select a conversation first");
    const optimistic: Message = { id: crypto.randomUUID(), conversation_id: conversationId, role, content, token_count: 0, created_at: new Date().toISOString() };
    setMessages((current) => [...current, optimistic]);
    try {
      const saved = await memoryService.addMessage(conversationId, role, content);
      setMessages((current) => current.map((message) => message.id === optimistic.id ? saved : message));
      return saved;
    } catch (addError) { setMessages((current) => current.filter((message) => message.id !== optimistic.id)); throw addError; }
  }

  return { messages, isLoading, error, add };
}