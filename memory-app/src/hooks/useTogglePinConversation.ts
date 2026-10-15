import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Conversation } from "../types/database";
import { supabase } from "../lib/supabase";
import { conversationKeys } from "./useConversations";

export function useTogglePinConversation(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, pinned }: { id: string; pinned: boolean }) => {
      const { data, error } = await supabase.from("conversations").update({ pinned } as never).eq("id", id).select().single();
      if (error) throw new Error(error.message);
      return data as Conversation;
    },
    onMutate: async ({ id, pinned }) => {
      if (!userId) return undefined;
      const key = conversationKeys.list(userId); await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Conversation[]>(key) ?? [];
      const next = previous.map((conversation) => conversation.id === id ? { ...conversation, pinned, updated_at: new Date().toISOString() } : conversation).sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updated_at.localeCompare(a.updated_at));
      queryClient.setQueryData(key, next); return { previous, key };
    },
    onError: (_error, _input, context) => { if (context) queryClient.setQueryData(context.key, context.previous); },
    onSettled: () => { if (userId) void queryClient.invalidateQueries({ queryKey: conversationKeys.list(userId) }); },
  });
}