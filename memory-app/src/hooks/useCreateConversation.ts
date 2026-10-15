import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Conversation } from "../types/database";
import { supabase } from "../lib/supabase";
import { MemoryService } from "../services/memory/MemoryService";
import { conversationKeys } from "./useConversations";

const memoryService = new MemoryService(supabase);
type CreateContext = { previous: Conversation[]; key: ReturnType<typeof conversationKeys.list> };

export function useCreateConversation(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation<Conversation, Error, string | undefined, CreateContext | undefined>({
    mutationFn: async (title: string | undefined = "New conversation") => { if (!userId) throw new Error("You must be signed in"); return memoryService.createConversation(userId, title); },
    onMutate: async (title: string | undefined = "New conversation") => {
      if (!userId) return undefined;
      const key = conversationKeys.list(userId); await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Conversation[]>(key) ?? []; const now = new Date().toISOString();
      const optimistic: Conversation = { id: `optimistic-${crypto.randomUUID()}`, user_id: userId, title, summary: null, pinned: false, message_count: 0, summarized_message_count: 0, created_at: now, updated_at: now };
      queryClient.setQueryData(key, [optimistic, ...previous]); return { previous, key };
    },
    onError: (_error, _title, context) => { if (context) queryClient.setQueryData(context.key, context.previous); },
    onSettled: () => { if (userId) void queryClient.invalidateQueries({ queryKey: conversationKeys.list(userId) }); },
  });
}