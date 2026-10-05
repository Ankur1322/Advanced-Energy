import { useEffect, useState } from "react";
import type { Conversation } from "../types/database";
import { supabase } from "../lib/supabase";
import { MemoryService } from "../services/memory/MemoryService";

const memoryService = new MemoryService(supabase);

export function useConversations(userId: string | undefined) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(Boolean(userId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) {
      setConversations([]);
      setIsLoading(false);
      return;
    }
    let active = true;
    setIsLoading(true);
    void supabase.from("conversations").select("*").eq("user_id", userId).order("pinned", { ascending: false }).order("updated_at", { ascending: false }).then(({ data, error: queryError }) => {
      if (!active) return;
      if (queryError) setError(queryError.message);
      else setConversations((data ?? []) as Conversation[]);
      setIsLoading(false);
    });
    const channel = supabase.channel(`conversations:${userId}`).on("postgres_changes", { event: "*", schema: "public", table: "conversations", filter: `user_id=eq.${userId}` }, () => {
      void supabase.from("conversations").select("*").eq("user_id", userId).order("pinned", { ascending: false }).order("updated_at", { ascending: false }).then(({ data }) => {
        if (active && data) setConversations(data as Conversation[]);
      });
    }).subscribe();
    return () => { active = false; void supabase.removeChannel(channel); };
  }, [userId]);

  async function create(title = "New conversation") {
    if (!userId) throw new Error("You must be signed in");
    const optimistic: Conversation = { id: crypto.randomUUID(), user_id: userId, title, summary: null, pinned: false, message_count: 0, summarized_message_count: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
    setConversations((current) => [optimistic, ...current]);
    try {
      const conversation = await memoryService.createConversation(userId, title);
      setConversations((current) => current.map((item) => item.id === optimistic.id ? conversation : item));
      return conversation;
    } catch (createError) {
      setConversations((current) => current.filter((item) => item.id !== optimistic.id));
      throw createError;
    }
  }

  async function update(id: string, values: Partial<Pick<Conversation, "title" | "pinned">>) {
    const previous = conversations;
    setConversations((current) => current.map((item) => item.id === id ? { ...item, ...values, updated_at: new Date().toISOString() } : item));
    const { data, error: updateError } = await supabase.from("conversations").update(values as never).eq("id", id).select().single();
    if (updateError) { setConversations(previous); throw new Error(updateError.message); }
    setConversations((current) => current.map((item) => item.id === id ? data as Conversation : item));
  }

  async function remove(id: string) {
    const previous = conversations;
    setConversations((current) => current.filter((item) => item.id !== id));
    try { await memoryService.deleteConversation(id); } catch (removeError) { setConversations(previous); throw removeError; }
  }

  return { conversations, isLoading, error, create, update, remove };
}