import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Conversation } from "../types/database";
import { supabase } from "../lib/supabase";
import { conversationKeys } from "./useConversations";

interface RenameInput { id: string; title: string; }

export function useRenameConversation(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, title }: RenameInput) => { const { data, error } = await supabase.from("conversations").update({ title } as never).eq("id", id).select().single(); if (error) throw new Error(error.message); return data as Conversation; },
    onMutate: async ({ id, title }) => { if (!userId) return undefined; const key = conversationKeys.list(userId); await queryClient.cancelQueries({ queryKey: key }); const previous = queryClient.getQueryData<Conversation[]>(key) ?? []; queryClient.setQueryData(key, previous.map((conversation) => conversation.id === id ? { ...conversation, title, updated_at: new Date().toISOString() } : conversation)); return { previous, key }; },
    onError: (_error, _input, context) => { if (context) queryClient.setQueryData(context.key, context.previous); },
    onSettled: () => { if (userId) void queryClient.invalidateQueries({ queryKey: conversationKeys.list(userId) }); },
  });
}