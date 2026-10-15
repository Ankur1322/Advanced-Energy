import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Conversation } from "../types/database";
import { supabase } from "../lib/supabase";
import { MemoryService } from "../services/memory/MemoryService";
import { conversationKeys } from "./useConversations";

const memoryService = new MemoryService(supabase);

export function useDeleteConversation(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => memoryService.deleteConversation(conversationId),
    onMutate: async (conversationId) => { if (!userId) return undefined; const key = conversationKeys.list(userId); await queryClient.cancelQueries({ queryKey: key }); const previous = queryClient.getQueryData<Conversation[]>(key) ?? []; queryClient.setQueryData(key, previous.filter((conversation) => conversation.id !== conversationId)); return { previous, key }; },
    onError: (_error, _conversationId, context) => { if (context) queryClient.setQueryData(context.key, context.previous); },
    onSettled: () => { if (userId) void queryClient.invalidateQueries({ queryKey: conversationKeys.list(userId) }); },
  });
}