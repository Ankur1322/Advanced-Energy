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
# Custom Styling — light, warm, Claude-inspired layout
# ============================================================================
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600&display=swap');

        /* ---- Global light theme ---- */
        .stApp {
            background-color: #F7F5F0;
            color: #2B2A27;
            font-family: 'Inter', sans-serif;
        }
        #MainMenu, footer, header {visibility: hidden;}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {
            background-color: #FBFAF7;
            border-right: 1px solid #E8E6DE;
        }
        section[data-testid="stSidebar"] * { color: #2B2A27; }

        /* Sidebar nav-style buttons (New chat / Chats) */
        section[data-testid="stSidebar"] .stButton button {
            width: 100%;
            text-align: left;
            background-color: transparent;
            color: #2B2A27;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 0.7rem;
            font-weight: 500;
            font-size: 0.92rem;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background-color: #EFEDE5;
        }
        section[data-testid="stSidebar"] .stButton button:focus:not(:active) {
            border: none;
            box-shadow: none;
        }

        /* Configuration expanders styled as clean rounded rows */
        section[data-testid="stSidebar"] div[data-testid="stExpander"] {
            background-color: #FFFFFF;
            border: 1px solid #E8E6DE;
            border-radius: 10px;
            margin-bottom: 8px;
        }
        section[data-testid="stSidebar"] details summary {
            font-weight: 500;
            font-size: 0.88rem;
            padding: 4px 2px;
        }

        .ae-section-label {
            color: #A6A399;
            font-size: 0.68rem;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            margin: 18px 4px 8px 4px;
        }

        /* ---- Logo mark ---- */
        .ae-logo-wrap {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            margin: 6px 0 22px 0;
        }
        .ae-logo-badge {
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: linear-gradient(135deg, #17B2A0, #2E86DE);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 6px rgba(23,178,160,0.35);
        }
        .ae-logo-tagline {
            font-size: 0.70rem;
            color: #A6A399;
            letter-spacing: 0.02em;
        }

        /* ---- Chats list ---- */
        .ae-chat-item {
            padding: 7px 10px;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #55534C;
            margin-bottom: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            cursor: pointer;
        }
        .ae-chat-item:hover { background-color: #EFEDE5; }
        .ae-chat-item.active { background-color: #EAF6F5; color: #12938A; font-weight: 500; }

        /* ---- Center greeting ---- */
        .ae-hero {
            text-align: center;
            margin-top: 8vh;
            margin-bottom: 1.6rem;
        }
        .ae-hero h1 {
            font-family: 'Lora', serif;
            font-style: italic;
            font-weight: 500;
            font-size: 2.3rem;
            color: #2B2A27;
            margin-bottom: 0.3rem;
        }
        .ae-hero p {
            color: #8A8778;
            font-size: 0.95rem;
        }

        /* ---- Input card (form) ---- */
        div[data-testid="stForm"] {
            background-color: #FFFFFF;
            border: 1px solid #E4E1D6;
            border-radius: 18px;
            padding: 14px 18px 10px 18px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.04);
            max-width: 760px;
            margin: 0 auto;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            background-color: transparent;
            border: none;
            color: #2B2A27;
            font-size: 1.02rem;
            padding: 4px 2px;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:focus {
            box-shadow: none;
            outline: none;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] {
            border-bottom: 1px solid #F0EEE6;
            padding-bottom: 8px;
            margin-bottom: 6px;
        }

        .ae-icon-btn {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            border: 1px solid #E4E1D6;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #8A8778;
            font-size: 0.95rem;
        }
        .ae-search-pill {
            border: 1px solid #E4E1D6;
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 0.82rem;
            color: #8A8778;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            width: fit-content;
        }

        div[data-testid="stForm"] button[kind="formSubmitButton"],
        div[data-testid="stForm"] button[data-testid="stFormSubmitButton"] {
            background: linear-gradient(135deg, #17B2A0, #2E86DE) !important;
            color: #fff !important;
            border-radius: 50% !important;
            width: 34px !important;
            height: 34px !important;
            border: none !important;
            padding: 0 !important;
            font-weight: 600;
        }

        /* Quick-prompt pills */
        .ae-pill-row { display: flex; gap: 8px; justify-content: center; margin-top: 14px; flex-wrap: wrap; }
        div[data-testid="column"] .stButton button {
            background-color: #FFFFFF;
            border: 1px solid #E4E1D6;
            border-radius: 20px;
            color: #55534C;
            font-size: 0.82rem;
            padding: 6px 14px;
        }
        div[data-testid="column"] .stButton button:hover {
            border-color: #17B2A0;
            color: #12938A;
        }

        /* ---- Answer card ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF;
            border: 1px solid #E8E6DE !important;
            border-radius: 14px;
        }

        /* ---- Tabs ---- */
        button[data-baseweb="tab"] { color: #8A8778; }
        button[data-baseweb="tab"][aria-selected="true"] { color: #12938A; }

        h1, h2, h3 { color: #2B2A27; font-family: 'Inter', sans-serif; }
    </style>
    """,
    unsafe_allow_html=True,
)

LOGO_HTML = """
<div class="ae-logo-wrap">
    <div class="ae-logo-badge">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M13 2L3 14h7l-1 8 11-14h-8l1-6z" fill="white"/>
        </svg>
    </div>
    <div class="ae-logo-tagline">Product Assistant</div>
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
                is_active = st.session_state.selected_chat_index == real_idx
                css_class = "ae-chat-item active" if is_active else "ae-chat-item"
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
# Main Content — centered greeting + rounded input card (Claude-style)
# ============================================================================
if not st.session_state.chat_history:
    st.markdown(
        """
        <div class='ae-hero'>
            <h1>⚡ Ask about our products</h1>
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
# Display Results
# ============================================================================
if st.session_state.chat_history:
    display_idx = (
        st.session_state.selected_chat_index
        if st.session_state.selected_chat_index is not None
        else len(st.session_state.chat_history) - 1
    )
    displayed = st.session_state.chat_history[display_idx]

    st.divider()
    st.subheader("Answer")
    with st.container(border=True):
        st.markdown(displayed["answer"])

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