import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Conversation } from "../types/database";
import { supabase } from "../lib/supabase";

export const conversationKeys = { all: ["conversations"] as const, list: (userId: string) => ["conversations", userId] as const };

async function fetchConversations(userId: string) {
  const { data, error } = await supabase.from("conversations").select("*").eq("user_id", userId).order("pinned", { ascending: false }).order("updated_at", { ascending: false });
  if (error) throw new Error(error.message);
  return (data ?? []) as Conversation[];
}

export function useConversations(userId: string | undefined) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: userId ? conversationKeys.list(userId) : ["conversations", "anonymous"], queryFn: () => fetchConversations(userId!), enabled: Boolean(userId) });

  useEffect(() => {
    if (!userId) return;
    const channel = supabase.channel(`conversations:${userId}`).on("postgres_changes", { event: "*", schema: "public", table: "conversations", filter: `user_id=eq.${userId}` }, () => { void queryClient.invalidateQueries({ queryKey: conversationKeys.list(userId) }); }).subscribe();
    return () => { void supabase.removeChannel(channel); };
  }, [queryClient, userId]);

  return { conversations: query.data ?? [], isLoading: query.isLoading, isFetching: query.isFetching, error: query.error instanceof Error ? query.error.message : null, refetch: query.refetch };
}