import { FormEvent, useState } from "react";
import { BrainCircuit, LoaderCircle, Send, Sparkles } from "lucide-react";
import type { Conversation, Message } from "../../types/database";
import { useMessages } from "../../hooks/useMessages";
import { useMemory } from "../../hooks/useMemory";
import { supabase } from "../../lib/supabase";
import { Button } from "../ui/Button";

export function ChatWorkspace({ userId, conversation, onFirstUserMessage }: { userId: string; conversation?: Conversation; onFirstUserMessage?: (content: string) => void }) {
  const { messages, isLoading, add } = useMessages(conversation?.id);
  const { context, isRetrieving, error: memoryError, retrieve, processTurn } = useMemory(userId, conversation?.id);
  const [draft, setDraft] = useState(""); const [isSending, setIsSending] = useState(false); const [error, setError] = useState<string | null>(null);
  async function send(event: FormEvent) {
    event.preventDefault(); const content = draft.trim(); if (!content || !conversation || isSending) return;
    setDraft(""); setError(null); setIsSending(true);
    try { const memoryContext = await retrieve(content); await add("user", content); onFirstUserMessage?.(content); const { data, error: responseError } = await supabase.functions.invoke("chat-response", { body: { message: content, context: memoryContext } }); if (responseError) throw responseError; const answer = String((data as { content?: string })?.content ?? "I could not generate a response."); await add("assistant", answer); void processTurn(content, answer); }
    catch (sendError) { setError(sendError instanceof Error ? sendError.message : "Unable to send message"); setDraft(content); } finally { setIsSending(false); }
  }
  return <main className="chat-workspace"><header className="chat-header"><div><p className="eyebrow">LONG-TERM MEMORY / {conversation ? "ACTIVE" : "IDLE"}</p><h2>{conversation?.title ?? "Select a conversation"}</h2></div><div className="memory-status"><BrainCircuit size={16} /><span>{isRetrieving ? "Retrieving context" : `${context?.memories.length ?? 0} memories linked`}</span></div></header><section className="message-stream">{!conversation && <div className="welcome"><Sparkles size={30} /><h3>Make the next answer more personal.</h3><p>Create a conversation to begin building a private, searchable memory layer.</p></div>}{conversation && isLoading && <LoaderCircle className="spin" />}{conversation && !isLoading && messages.map((message) => <MessageBubble key={message.id} message={message} />)}</section>{memoryError && <p className="error-text">Memory: {memoryError}</p>}{error && <p className="error-text">{error}</p>}<form className="composer" onSubmit={send}><textarea aria-label="Message" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={conversation ? "Ask something worth remembering..." : "Choose a conversation first"} disabled={!conversation || isSending} rows={1} /><Button aria-label="Send message" className="send-button" type="submit" disabled={!conversation || !draft.trim() || isSending}>{isSending ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}</Button></form><p className="composer-note">Private by design · important facts are extracted selectively</p></main>;
}

function MessageBubble({ message }: { message: Message }) { return <article className={`message ${message.role}`}><span className="message-label">{message.role === "assistant" ? "AE MEMORY" : "YOU"}</span><p>{message.content}</p></article>; }