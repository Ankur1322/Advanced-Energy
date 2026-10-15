import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Message, MessageRole } from "../types/database";
import { supabase } from "../lib/supabase";
import { MemoryService } from "../services/memory/MemoryService";
import { conversationKeys } from "./useConversations";

const memoryService = new MemoryService(supabase);
export const messageKeys = { list: (conversationId: string) => ["messages", conversationId] as const };

export function useMessages(conversationId: string | undefined) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: conversationId ? messageKeys.list(conversationId) : ["messages", "none"], queryFn: () => memoryService.getConversationHistory(conversationId!), enabled: Boolean(conversationId) });
  useEffect(() => {
    if (!conversationId) return;
    const channel = supabase.channel(`messages:${conversationId}`).on("postgres_changes", { event: "INSERT", schema: "public", table: "messages", filter: `conversation_id=eq.${conversationId}` }, (payload: any) => {
      queryClient.setQueryData<Message[]>(messageKeys.list(conversationId), (current = []) => current.some((message) => message.id === payload.new.id) ? current : [...current, payload.new as Message]);
    }).subscribe();
    return () => { void supabase.removeChannel(channel); };
  }, [conversationId, queryClient]);
  const addMutation = useMutation({
    mutationFn: ({ role, content }: { role: MessageRole; content: string }) => memoryService.addMessage(conversationId!, role, content),
    onMutate: async ({ role, content }) => { if (!conversationId) return undefined; const key = messageKeys.list(conversationId); await queryClient.cancelQueries({ queryKey: key }); const previous = queryClient.getQueryData<Message[]>(key) ?? []; const optimistic: Message = { id: `optimistic-${crypto.randomUUID()}`, conversation_id: conversationId, role, content, token_count: 0, created_at: new Date().toISOString() }; queryClient.setQueryData(key, [...previous, optimistic]); return { previous, key }; },
    onError: (_error, _input, context) => { if (context) queryClient.setQueryData(context.key, context.previous); },
    onSettled: () => { if (conversationId) { void queryClient.invalidateQueries({ queryKey: messageKeys.list(conversationId) }); void queryClient.invalidateQueries({ queryKey: conversationKeys.all }); } },
  });
  return { messages: query.data ?? [], isLoading: query.isLoading, error: query.error instanceof Error ? query.error.message : null, add: (role: MessageRole, content: string) => addMutation.mutateAsync({ role, content }) };
}