import { useEffect, useState } from "react";
import { ConversationSidebar } from "./components/chat/ConversationSidebar";
import { ChatWorkspace } from "./components/chat/ChatWorkspace";
import { useConversations } from "./hooks/useConversations";
import { supabase } from "./lib/supabase";

export default function App() {
  const [userId, setUserId] = useState<string>();
  const [activeId, setActiveId] = useState<string>();
  const [authError, setAuthError] = useState<string>();
  const conversationsState = useConversations(userId);
  useEffect(() => { void supabase.auth.getUser().then(({ data, error }) => { if (error) setAuthError(error.message); else setUserId(data.user?.id); }); }, []);
  useEffect(() => { if (!activeId && conversationsState.conversations[0]) setActiveId(conversationsState.conversations[0].id); }, [activeId, conversationsState.conversations]);
  const activeConversation = conversationsState.conversations.find((conversation) => conversation.id === activeId);
  if (authError) return <div className="auth-screen"><h1>Memory needs a signed-in session.</h1><p>{authError}</p></div>;
  if (!userId) return <div className="auth-screen"><div className="auth-mark">AE</div><h1>Your conversations, with continuity.</h1><p>Sign in through Supabase to activate your private memory workspace.</p></div>;
  return <div className="app-shell"><ConversationSidebar conversations={conversationsState.conversations} activeId={activeId} isLoading={conversationsState.isLoading} onSelect={setActiveId} onCreate={async () => { const conversation = await conversationsState.create(); setActiveId(conversation.id); }} onUpdate={conversationsState.update} onDelete={async (id) => { await conversationsState.remove(id); if (id === activeId) setActiveId(undefined); }} /><ChatWorkspace userId={userId} conversation={activeConversation} /></div>;
}