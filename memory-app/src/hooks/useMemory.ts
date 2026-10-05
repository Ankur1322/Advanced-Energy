import { useState } from "react";
import { supabase } from "../lib/supabase";
import { MemoryService } from "../services/memory/MemoryService";
import type { MemoryContext } from "../services/memory/types";

const memoryService = new MemoryService(supabase);

export function useMemory(userId: string | undefined, conversationId: string | undefined) {
  const [context, setContext] = useState<MemoryContext | null>(null);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function retrieve(query: string) {
    if (!userId || !conversationId) return null;
    setIsRetrieving(true); setError(null);
    try { const next = await memoryService.buildMemoryContext(query, userId, conversationId); setContext(next); return next; }
    catch (retrieveError) { const message = retrieveError instanceof Error ? retrieveError.message : "Memory retrieval failed"; setError(message); throw retrieveError; }
    finally { setIsRetrieving(false); }
  }

  async function processTurn(userMessage: string, assistantMessage: string) {
    if (!userId || !conversationId) return [];
    try {
      const stored = await memoryService.extractAndStoreMemories(userMessage, assistantMessage, userId, conversationId);
      void memoryService.updateConversationSummary(conversationId);
      return stored;
    }
    catch (processError) { setError(processError instanceof Error ? processError.message : "Memory processing failed"); return []; }
  }

  return { context, isRetrieving, error, retrieve, processTurn };
}