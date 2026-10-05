import { useState } from "react";
import { Archive, Edit3, MessageSquarePlus, Pin, Trash2 } from "lucide-react";
import type { Conversation } from "../../types/database";
import { Button } from "../ui/Button";

interface Props { conversations: Conversation[]; activeId?: string; isLoading: boolean; onSelect: (id: string) => void; onCreate: () => Promise<unknown>; onUpdate: (id: string, values: Partial<Pick<Conversation, "title" | "pinned">>) => Promise<void>; onDelete: (id: string) => Promise<void>; }

export function ConversationSidebar({ conversations, activeId, isLoading, onSelect, onCreate, onUpdate, onDelete }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  return <aside className="sidebar">
    <div className="sidebar-header"><div><p className="eyebrow">AE / MEMORY</p><h1>Conversations</h1></div><Button aria-label="New conversation" className="icon-button" onClick={() => void onCreate()}><MessageSquarePlus size={18} /></Button></div>
    <div className="conversation-list">
      {isLoading && <p className="muted">Loading memory threads...</p>}
      {!isLoading && conversations.length === 0 && <div className="empty-state"><Archive size={22} /><p>Your memory archive is quiet.</p></div>}
      {conversations.map((conversation) => <div className={`conversation-item ${conversation.id === activeId ? "active" : ""}`} key={conversation.id} onClick={() => onSelect(conversation.id)}>
        {editingId === conversation.id ? <input autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { void onUpdate(conversation.id, { title: draft || "New conversation" }); setEditingId(null); } }} onBlur={() => setEditingId(null)} /> : <><div className="conversation-title"><span>{conversation.pinned && <Pin size={12} />} {conversation.title}</span><div className="item-actions"><button aria-label="Rename conversation" onClick={(event) => { event.stopPropagation(); setEditingId(conversation.id); setDraft(conversation.title); }}><Edit3 size={13} /></button><button aria-label="Pin conversation" onClick={(event) => { event.stopPropagation(); void onUpdate(conversation.id, { pinned: !conversation.pinned }); }}><Pin size={13} /></button><button aria-label="Delete conversation" onClick={(event) => { event.stopPropagation(); void onDelete(conversation.id); }}><Trash2 size={13} /></button></div></div><p>{conversation.preview ?? conversation.summary ?? "No messages yet"}</p><time>{new Date(conversation.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time></>}
      </div>)}
    </div>
  </aside>;
}