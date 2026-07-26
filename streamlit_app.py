#!/usr/bin/env python3
"""
Advanced Energy Products RAG Chatbot - Streamlit UI
====================================================
Interactive web-based Q&A interface for Advanced Energy products.

Run with:
    streamlit run streamlit_app.py
"""

import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"

import streamlit as st
import chromadb
import google.generativeai as genai
from embed_to_chroma import COLLECTION_NAME, DB_DIR, TfidfSvdEmbeddingFunction

# ============================================================================
# Page Configuration
# ============================================================================
st.set_page_config(
    page_title="Advanced Energy Q&A Bot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Custom Styling — deep indigo/slate dark theme, amber-violet accent
# ============================================================================
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

        :root {
            --bg: #0E1016;
            --surface: #171A23;
            --surface-2: #1E2230;
            --border: #2A2E3D;
            --text: #E8E9EE;
            --muted: #8B90A3;
            --accent-1: #F5A85B;
            --accent-2: #8B7CF6;
            --accent-grad: linear-gradient(135deg, #F5A85B 0%, #EF6F8E 45%, #8B7CF6 100%);
            --success: #34D399;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
        }
        #MainMenu, footer, header {visibility: hidden;}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {
            background: var(--surface);
            border-right: 1px solid var(--border);
        }
        section[data-testid="stSidebar"] * { color: var(--text); }

        section[data-testid="stSidebar"] .stButton button {
            width: 100%;
            text-align: left;
            background-color: transparent;
            color: var(--text);
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 0.55rem 0.75rem;
            font-weight: 500;
            font-size: 0.9rem;
            transition: all 0.15s ease;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background-color: var(--surface-2);
            border-color: var(--border);
        }
        section[data-testid="stSidebar"] .stButton button:focus:not(:active) {
            box-shadow: none;
        }

        section[data-testid="stSidebar"] div[data-testid="stExpander"] {
            background-color: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 10px;
        }
        section[data-testid="stSidebar"] details summary {
            font-weight: 500;
            font-size: 0.86rem;
            padding: 6px 4px;
        }

        .ae-section-label {
            color: var(--muted);
            font-size: 0.68rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin: 20px 4px 10px 4px;
            font-weight: 600;
        }

        /* ---- Logo mark ---- */
        .ae-logo-wrap {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 4px 2px 20px 2px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 16px;
        }
        .ae-logo-badge {
            width: 38px;
            height: 38px;
            border-radius: 11px;
            background: var(--accent-grad);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 14px rgba(245, 168, 91, 0.25);
            flex-shrink: 0;
        }
        .ae-logo-title {
            font-family: 'Sora', sans-serif;
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--text);
            line-height: 1.1;
        }
        .ae-logo-tagline {
            font-size: 0.68rem;
            color: var(--muted);
            margin-top: 2px;
        }

        /* ---- Chats list ---- */
        .ae-chat-item {
            padding: 8px 10px;
            border-radius: 9px;
            font-size: 0.85rem;
            color: #B7BACB;
            margin-bottom: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            cursor: pointer;
            border: 1px solid transparent;
        }
        .ae-chat-item:hover { background-color: var(--surface-2); }
        .ae-chat-item.active {
            background-color: rgba(139, 124, 246, 0.12);
            border-color: rgba(139, 124, 246, 0.35);
            color: #C9C1FB;
            font-weight: 500;
        }

        /* ---- Center greeting ---- */
        .ae-hero {
            text-align: center;
            margin-top: 7vh;
            margin-bottom: 1.8rem;
        }
        .ae-hero .ae-hero-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 54px;
            height: 54px;
            border-radius: 16px;
            background: var(--accent-grad);
            box-shadow: 0 8px 24px rgba(245, 168, 91, 0.25);
            margin-bottom: 18px;
            font-size: 1.5rem;
        }
        .ae-hero h1 {
            font-family: 'Sora', sans-serif;
            font-weight: 700;
            font-size: 2.1rem;
            color: var(--text);
            margin-bottom: 0.4rem;
            letter-spacing: -0.02em;
        }
        .ae-hero p {
            color: var(--muted);
            font-size: 0.95rem;
        }

        /* ---- Input card (form) ---- */
        div[data-testid="stForm"] {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 12px 16px 8px 16px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.25);
            max-width: 760px;
            margin: 0 auto;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            background-color: transparent;
            border: none;
            color: var(--text);
            font-size: 1rem;
            padding: 6px 4px;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:focus {
            box-shadow: none;
            outline: none;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] {
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            margin-bottom: 6px;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input::placeholder {
            color: var(--muted);
        }

        .ae-icon-btn {
            width: 30px;
            height: 30px;
            border-radius: 9px;
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--muted);
            font-size: 0.9rem;
            background: var(--surface-2);
        }
        .ae-search-pill {
            border: 1px solid var(--border);
            background: var(--surface-2);
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 0.8rem;
            color: var(--muted);
            display: inline-flex;
            align-items: center;
            gap: 4px;
            width: fit-content;
        }

        div[data-testid="stForm"] button[kind="formSubmitButton"],
        div[data-testid="stForm"] button[data-testid="stFormSubmitButton"] {
            background: var(--accent-grad) !important;
            color: #1A1206 !important;
            border-radius: 11px !important;
            width: 36px !important;
            height: 36px !important;
            border: none !important;
            padding: 0 !important;
            font-weight: 700;
        }

        /* Quick-prompt pills */
        .ae-pill-row { display: flex; gap: 10px; justify-content: center; margin-top: 16px; flex-wrap: wrap; }
        div[data-testid="column"] .stButton button {
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            color: #B7BACB;
            font-size: 0.82rem;
            padding: 7px 15px;
            transition: all 0.15s ease;
        }
        div[data-testid="column"] .stButton button:hover {
            border-color: var(--accent-2);
            color: #C9C1FB;
            background-color: rgba(139, 124, 246, 0.08);
        }

        /* ---- Message bubbles ---- */
        .ae-msg-row { display: flex; gap: 12px; margin-bottom: 22px; align-items: flex-start; }
        .ae-msg-row.user { flex-direction: row-reverse; }

        .ae-avatar {
            width: 32px;
            height: 32px;
            border-radius: 9px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.95rem;
            flex-shrink: 0;
        }
        .ae-avatar.assistant { background: var(--accent-grad); }
        .ae-avatar.user { background: var(--surface-2); border: 1px solid var(--border); }

        .ae-msg-bubble {
            max-width: 78%;
            padding: 12px 16px;
            border-radius: 14px;
            font-size: 0.92rem;
            line-height: 1.65;
        }
        .ae-msg-bubble.assistant {
            background: var(--surface);
            border: 1px solid var(--border);
            border-top-left-radius: 4px;
            color: var(--text);
        }
        .ae-msg-bubble.user {
            background: rgba(139, 124, 246, 0.12);
            border: 1px solid rgba(139, 124, 246, 0.3);
            border-top-right-radius: 4px;
            color: #E4E1FB;
        }

        /* ---- Sources badge row ---- */
        .ae-source-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 4px 10px;
            font-size: 0.75rem;
            color: var(--muted);
            margin: 2px 4px 2px 0;
        }

        /* ---- Answer / context cards ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--surface);
            border: 1px solid var(--border) !important;
            border-radius: 14px;
        }

        /* ---- Tabs ---- */
        button[data-baseweb="tab"] { color: var(--muted); }
        button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent-2); }
        div[data-baseweb="tab-highlight"] { background-color: var(--accent-2) !important; }

        h1, h2, h3 { color: var(--text); font-family: 'Sora', sans-serif; }

        hr { border-color: var(--border) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

LOGO_HTML = """
<div class="ae-logo-wrap">
    <div class="ae-logo-badge">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M13 2L3 14h7l-1 8 11-14h-8l1-6z" fill="#1A1206"/>
        </svg>
    </div>
    <div>
        <div class="ae-logo-title">Advanced Energy</div>
        <div class="ae-logo-tagline">Product Assistant</div>
    </div>
</div>
"""

# ============================================================================
# Session State Management
# ============================================================================
if "api_key_configured" not in st.session_state:
    st.session_state.api_key_configured = False

if "using_mock_mode" not in st.session_state:
    st.session_state.using_mock_mode = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "db_loaded" not in st.session_state:
    st.session_state.db_loaded = False

if "show_chats" not in st.session_state:
    st.session_state.show_chats = False

if "selected_chat_index" not in st.session_state:
    st.session_state.selected_chat_index = None

if "prefill_query" not in st.session_state:
    st.session_state.prefill_query = ""

# ============================================================================
# Helper Functions
# ============================================================================
@st.cache_resource
def load_embedding_model(db_dir: Path):
    """Load the fitted embedding model from disk (cached for performance)."""
    model_path = db_dir / "embedding_model.pkl"
    if not model_path.exists():
        return None
    return TfidfSvdEmbeddingFunction.load(model_path)


@st.cache_resource
def load_chromadb_client(db_dir: Path):
    """Initialize ChromaDB client (cached)."""
    return chromadb.PersistentClient(path=str(db_dir))


def setup_gemini_api(api_key: str = None) -> bool:
    """Configure Gemini API. Returns True if successful."""
    try:
        if api_key:
            genai.configure(api_key=api_key)
        elif os.environ.get("GEMINI_API_KEY", "").strip():
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        else:
            return False
        st.session_state.api_key_configured = True
        st.session_state.using_mock_mode = False
        return True
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}")
        return False


def get_llm_response(prompt: str, context: str, query: str, retries: int = 3) -> str:
    """Send prompt to Gemini with retry logic."""
    if st.session_state.using_mock_mode:
        response = (
            f"🤖 **[Offline/Mock Assistant Response]**\n\n"
            f"Here is the most relevant matching information found in our database for your question:\n\n"
        )
        lines = context.splitlines()
        found_any = False
        for line in lines:
            if any(
                term in line.lower()
                for term in ("subproduct:", "category:", "description:", "total subproducts:")
            ) or "Category:" in line:
                response += f"• {line}\n"
                found_any = True
        if not found_any:
            response += f"**Matches found:**\n{context[:300]}..."
        response += (
            "\n\n*To get a fully natural AI answer, set your GEMINI_API_KEY in the sidebar!*"
        )
        return response

    models_to_try = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-pro-latest",
        "gemini-1.5-flash",
        "gemini-pro",
    ]

    for model_name in models_to_try:
        for attempt in range(1, retries + 1):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                err_msg = str(e)
                if "404" in err_msg or "not found" in err_msg:
                    break
                elif "429" in err_msg or "Too Many Requests" in err_msg:
                    delay = 5 * (2 ** (attempt - 1))
                    time.sleep(delay)
                else:
                    raise e

    raise Exception("Could not find a supported Gemini model or exceeded retries.")


def ask_question(query: str, db_client, embedding_func, n_results: int = 5) -> tuple[str, list]:
    """
    Query ChromaDB and generate answer with Gemini.
    Returns (answer, context_blocks).
    """
    query_emb = embedding_func([query])
    collection = db_client.get_or_create_collection(name=COLLECTION_NAME)
    results = collection.query(query_embeddings=query_emb, n_results=n_results)

    context_blocks = []
    for idx, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        type_str = meta.get("type", "unknown")
        category = meta.get("category", "")
        subproduct = meta.get("subproduct", "")
        source_link = meta.get("source_link", "")

        block = {
            "index": idx,
            "type": type_str,
            "category": category,
            "subproduct": subproduct,
            "source_link": source_link,
            "content": doc,
        }
        context_blocks.append(block)

    context = "\n".join(
        [
            f"--- Context Source {b['index']} ({b['type']}) ---\n"
            f"Category: {b['category']}\n"
            f"Subproduct: {b['subproduct']}\n"
            f"Content:\n{b['content']}\n"
            for b in context_blocks
        ]
    )

    if not context.strip():
        return (
            "I don't have enough information in the available documents to answer that question.",
            context_blocks,
        )

    prompt = f"""You are an expert product assistant for Advanced Energy.

You must answer ONLY using the information provided in the retrieved context below.
Do not use any external knowledge, prior training data, or general information about
Advanced Energy, its products, or the industry — even if you believe you know the answer.

Rules you must follow strictly:
1. Only use facts explicitly present in the retrieved context to answer the user's question.
2. If the retrieved context does not contain enough information to answer the question,
   respond with: "I don't have enough information in the available documents to answer that question."
3. Never fabricate product names, specifications, categories, or details.
4. If the question is unrelated to the retrieved context or to Advanced Energy's products,
   respond with: "I can only answer questions based on the provided product documentation."
5. Always mention the specific product name(s) and category/categories exactly as they appear.
6. Do not speculate about information that might exist elsewhere.
7. If multiple retrieved chunks conflict, point out the discrepancy.

Retrieved Context:
{context}

User Question:
{query}

Answer using only the above context, following all rules strictly.
"""

    answer = get_llm_response(prompt, context, query)
    return answer, context_blocks


# ============================================================================
# Sidebar — logo, New chat, Chats, API key, Retrieval Settings ONLY
# ============================================================================
with st.sidebar:
    st.markdown(LOGO_HTML, unsafe_allow_html=True)

    if st.button("＋  New chat", key="new_chat_btn", use_container_width=True):
        st.session_state.selected_chat_index = None
        st.session_state.prefill_query = ""
        st.session_state.show_chats = False
        st.rerun()

    if st.button("💬  Chats", key="chats_toggle_btn", use_container_width=True):
        st.session_state.show_chats = not st.session_state.show_chats

    if st.session_state.show_chats:
        if st.session_state.chat_history:
            for i, entry in enumerate(reversed(st.session_state.chat_history)):
                real_idx = len(st.session_state.chat_history) - 1 - i
                label = entry["question"]
                if len(label) > 30:
                    label = label[:30] + "…"
                if st.button(label, key=f"chat_item_{real_idx}", use_container_width=True):
                    st.session_state.selected_chat_index = real_idx
                    st.rerun()
        else:
            st.markdown("<div class='ae-chat-item'>No chats yet</div>", unsafe_allow_html=True)

    st.markdown("<div class='ae-section-label'>Configuration</div>", unsafe_allow_html=True)

    with st.expander("🔑  API Key", expanded=False):
        api_key_input = st.text_input(
            "Enter your Gemini API key:",
            type="password",
            key="api_key_input",
            help="Get your key at https://aistudio.google.com/app/apikey",
        )

        if api_key_input:
            if setup_gemini_api(api_key_input):
                st.success("✅ Gemini API configured!")
        else:
            if os.environ.get("GEMINI_API_KEY"):
                if setup_gemini_api():
                    st.info("✅ Using Gemini API from environment variable")
            else:
                st.session_state.using_mock_mode = True
                st.warning("⚠️ Running in Offline Mock Mode.")

    with st.expander("⚙️  Retrieval Settings", expanded=False):
        n_results = st.slider(
            "Documents to retrieve:",
            min_value=1,
            max_value=10,
            value=5,
            help="Higher values provide more context but may dilute relevance",
        )

# ============================================================================
# Initialize Database (silent — no visible sidebar panel)
# ============================================================================
if not st.session_state.db_loaded:
    try:
        ef = load_embedding_model(DB_DIR)
        if ef is None:
            st.error("❌ Embedding model not found. Run `python embed_to_chroma.py` first.")
            st.stop()

        client = load_chromadb_client(DB_DIR)

        st.session_state.db_loaded = True
        st.session_state.ef = ef
        st.session_state.client = client
        st.session_state.embedding_func = ef

    except Exception as e:
        st.error(f"❌ Failed to load database: {e}")
        st.stop()

# ============================================================================
# Main Content — centered greeting + rounded input card
# ============================================================================
if not st.session_state.chat_history:
    st.markdown(
        """
        <div class='ae-hero'>
            <div class="ae-hero-badge">⚡</div>
            <h1>Ask about our products</h1>
            <p>Answers are generated only from Advanced Energy's product documentation.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.form("ask_form", clear_on_submit=True):
    query = st.text_input(
        "Ask anything about our products",
        value=st.session_state.prefill_query,
        placeholder="How can I help you today?",
        key="query_input",
        label_visibility="collapsed",
    )
    icon_cols = st.columns([1, 1, 3, 6, 1])
    with icon_cols[0]:
        st.markdown("<div class='ae-icon-btn'>＋</div>", unsafe_allow_html=True)
    with icon_cols[1]:
        st.markdown("<div class='ae-icon-btn'>⚙</div>", unsafe_allow_html=True)
    with icon_cols[2]:
        st.markdown("<div class='ae-search-pill'>🔍 Search</div>", unsafe_allow_html=True)
    with icon_cols[4]:
        submitted = st.form_submit_button("➤")

if not st.session_state.chat_history:
    st.markdown("<div class='ae-pill-row'>", unsafe_allow_html=True)
    pill_cols = st.columns(4)
    quick_prompts = ["Product categories", "High voltage supplies", "Plasma power products", "Compare converters"]
    for col, label in zip(pill_cols, quick_prompts):
        with col:
            if st.button(label, key=f"pill_{label}"):
                st.session_state.prefill_query = label
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

if submitted and query:
    st.session_state.prefill_query = ""
    with st.spinner("Thinking..."):
        try:
            answer, context_blocks = ask_question(
                query,
                st.session_state.client,
                st.session_state.embedding_func,
                n_results=n_results,
            )

            st.session_state.chat_history.append(
                {
                    "question": query,
                    "answer": answer,
                    "context_blocks": context_blocks,
                }
            )
            st.session_state.selected_chat_index = len(st.session_state.chat_history) - 1

        except Exception as e:
            st.error(f"❌ Error processing question: {e}")
            st.stop()

# ============================================================================
# Display Results — chat-bubble style
# ============================================================================
if st.session_state.chat_history:
    display_idx = (
        st.session_state.selected_chat_index
        if st.session_state.selected_chat_index is not None
        else len(st.session_state.chat_history) - 1
    )
    displayed = st.session_state.chat_history[display_idx]

    st.markdown("<div style='max-width: 820px; margin: 24px auto 0 auto;'>", unsafe_allow_html=True)

    # User question bubble
    st.markdown(
        f"""
        <div class="ae-msg-row user">
            <div class="ae-avatar user">🧑</div>
            <div class="ae-msg-bubble user">{displayed['question']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Assistant answer bubble
    st.markdown(
        f"""
        <div class="ae-msg-row assistant">
            <div class="ae-avatar assistant">⚡</div>
            <div class="ae-msg-bubble assistant">{displayed['answer']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Source pills summary
    if displayed["context_blocks"]:
        pills_html = "".join(
            f"<span class='ae-source-pill'>📄 {b['subproduct'] or b['category'] or 'Source ' + str(b['index'])}</span>"
            for b in displayed["context_blocks"]
        )
        st.markdown(
            f"<div style='margin: 4px 0 20px 44px;'>{pills_html}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("Retrieved Context")

    tabs = st.tabs([f"Source {i + 1}" for i in range(len(displayed["context_blocks"]))])

    for tab, block in zip(tabs, displayed["context_blocks"]):
        with tab:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Type:** `{block['type']}`")
                if block["category"]:
                    st.markdown(f"**Category:** {block['category']}")
            with col2:
                if block["subproduct"]:
                    st.markdown(f"**Subproduct:** {block['subproduct']}")
                if block["source_link"]:
                    st.markdown(
                        f"**Source:** [Link]({block['source_link']})"
                        if block["source_link"] != "Not found"
                        else "**Source:** Not found"
                    )

            st.divider()
            st.markdown("**Content:**")
            st.markdown(block["content"])