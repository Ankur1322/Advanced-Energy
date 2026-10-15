import { useEffect, useState } from "react";
import { ChatHistorySidebar } from "./components/chat/ChatHistorySidebar";
import { ChatWorkspace } from "./components/chat/ChatWorkspace";
import { useConversations } from "./hooks/useConversations";
import { useCreateConversation } from "./hooks/useCreateConversation";
import { useDeleteConversation } from "./hooks/useDeleteConversation";
import { useRenameConversation } from "./hooks/useRenameConversation";
import { useTogglePinConversation } from "./hooks/useTogglePinConversation";
import { isSupabaseConfigured, supabase } from "./lib/supabase";
import type { Conversation } from "./types/database";

export default function App() {
  const [userId, setUserId] = useState<string>();
  const [activeId, setActiveId] = useState<string>();
  const [authError, setAuthError] = useState<string>();
  const conversationsState = useConversations(userId);
  const createConversation = useCreateConversation(userId);
  const deleteConversation = useDeleteConversation(userId);
  const renameConversation = useRenameConversation(userId);
  const togglePinConversation = useTogglePinConversation(userId);
  useEffect(() => {
    void supabase.auth.getUser().then((result: { data: { user?: { id: string } | null }; error?: { message?: string } | null }) => {
      const { data, error } = result;
      if (error) setAuthError(error.message ?? "Unable to load the current user.");
      else setUserId(data.user?.id);
    });
  }, []);
  useEffect(() => { if (!activeId && conversationsState.conversations[0]) setActiveId(conversationsState.conversations[0].id); }, [activeId, conversationsState.conversations]);
  const activeConversation = conversationsState.conversations.find((conversation) => conversation.id === activeId);
  if (!isSupabaseConfigured) return <div className="auth-screen"><div className="auth-mark">AE</div><h1>Supabase needs to be configured.</h1><p>Add your project URL and anon key to memory-app/.env.local to activate chat history and memory features.</p><p className="muted">Required values: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY</p></div>;
  if (authError) return <div className="auth-screen"><h1>Memory needs a signed-in session.</h1><p>{authError}</p></div>;
  if (!userId) return <div className="auth-screen"><div className="auth-mark">AE</div><h1>Your conversations, with continuity.</h1><p>Sign in through Supabase to activate your private memory workspace.</p></div>;
  const handleCreate = () => { void createConversation.mutateAsync(undefined).then((conversation) => setActiveId(conversation.id)); };
  const handleDelete = (conversation: Conversation) => { void deleteConversation.mutateAsync(conversation.id).then(() => { if (conversation.id === activeId) setActiveId(undefined); }); };
  const handleRename = (conversation: Conversation) => { const title = window.prompt("Rename chat", conversation.title)?.trim(); if (title && title !== conversation.title) void renameConversation.mutateAsync({ id: conversation.id, title }); };
  return <div className="app-shell"><ChatHistorySidebar conversations={conversationsState.conversations} activeId={activeId} isLoading={conversationsState.isLoading} isMutating={createConversation.isPending || deleteConversation.isPending} error={conversationsState.error} onSelect={setActiveId} onCreate={handleCreate} onRename={handleRename} onTogglePin={(conversation) => { void togglePinConversation.mutateAsync({ id: conversation.id, pinned: !conversation.pinned }); }} onDelete={handleDelete} /><ChatWorkspace userId={userId} conversation={activeConversation} onFirstUserMessage={(content) => { if (activeConversation?.title === "New conversation") void renameConversation.mutateAsync({ id: activeConversation.id, title: makeConversationTitle(content) }); }} /></div>;
}

function makeConversationTitle(content: string) { const normalized = content.replace(/\s+/g, " ").trim(); return normalized.length > 48 ? `${normalized.slice(0, 48).trimEnd()}...` : normalized || "New conversation"; }