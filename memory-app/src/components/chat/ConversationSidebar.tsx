import { useState } from "react";
import { Archive, LoaderCircle, MessageSquarePlus, MoreHorizontal, Pencil, Pin, Trash2 } from "lucide-react";
import type { Conversation } from "../../types/database";
import { Button } from "../ui/Button";

interface Props {
  conversations: Conversation[];
  activeId?: string;
  isLoading: boolean;
  isMutating?: boolean;
  error?: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (conversation: Conversation) => void;
  onTogglePin: (conversation: Conversation) => void;
  onDelete: (conversation: Conversation) => void;
}

export function ConversationSidebar({ conversations, activeId, isLoading, isMutating, error, onSelect, onCreate, onRename, onTogglePin, onDelete }: Props) {
  const [menuId, setMenuId] = useState<string | null>(null);
  return <aside className="sidebar">
    <div className="sidebar-header"><div><p className="eyebrow">AE / MEMORY</p><h1>Chats</h1></div><Button aria-label="New chat" className="icon-button" onClick={onCreate} disabled={isMutating}><MessageSquarePlus size={17} /></Button></div>
    {error && <p className="sidebar-error">Could not load chats</p>}
    <div className="conversation-list" aria-live="polite">
      {isLoading && <div className="sidebar-status"><LoaderCircle className="spin" size={16} /><span>Loading chats</span></div>}
      {!isLoading && conversations.length === 0 && <div className="empty-state"><Archive size={20} /><p>No chats yet</p><button onClick={onCreate}>Start a new chat</button></div>}
      {conversations.map((conversation) => <div className={`conversation-item ${conversation.id === activeId ? "active" : ""}`} key={conversation.id} onClick={() => onSelect(conversation.id)}>
        <div className="conversation-title"><span>{conversation.pinned && <Pin className="pin-mark" size={11} />}{conversation.title}</span><button className="more-button" aria-label={`Actions for ${conversation.title}`} onClick={(event) => { event.stopPropagation(); setMenuId(menuId === conversation.id ? null : conversation.id); }}><MoreHorizontal size={15} /></button></div>
        <p>{conversation.preview ?? conversation.summary ?? "New conversation"}</p>
        <time>{formatDate(conversation.updated_at)}</time>
        {menuId === conversation.id && <div className="conversation-menu" onClick={(event) => event.stopPropagation()}><button onClick={() => { onRename(conversation); setMenuId(null); }}><Pencil size={13} /> Rename</button><button onClick={() => { onTogglePin(conversation); setMenuId(null); }}><Pin size={13} /> {conversation.pinned ? "Unpin" : "Pin"}</button><button className="danger" onClick={() => { onDelete(conversation); setMenuId(null); }}><Trash2 size={13} /> Delete</button></div>}
      </div>)}
    </div>
  </aside>;
}

function formatDate(value: string) { const date = new Date(value); const today = new Date(); return date.toDateString() === today.toDateString() ? date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : date.toLocaleDateString(undefined, { month: "short", day: "numeric" }); }