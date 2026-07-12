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
# Custom Dashboard Styling (dark, sidebar-driven layout)
# ============================================================================
st.markdown(
    """
    <style>
        /* ---- Global dark theme ---- */
        .stApp {
            background-color: #0d1117;
            color: #e6edf3;
        }
        #MainMenu, footer, header {visibility: hidden;}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {
            background-color: #12161c;
            border-right: 1px solid #22272e;
        }
        section[data-testid="stSidebar"] .stButton button {
            width: 100%;
            text-align: left;
            background-color: #1b2530;
            color: #e6edf3;
            border: 1px solid #263140;
            border-radius: 10px;
            padding: 0.55rem 0.9rem;
            margin-bottom: 6px;
            font-weight: 500;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background-color: #17b2a0;
            border-color: #17b2a0;
            color: #041014;
        }

        /* ---- Recents list items ---- */
        .ae-recent-item {
            padding: 6px 10px;
            border-radius: 8px;
            color: #9aa7b2;
            font-size: 0.85rem;
            margin-bottom: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            cursor: default;
        }
        .ae-recent-item:hover {
            background-color: #1b2530;
            color: #e6edf3;
        }
        .ae-section-label {
            color: #5b6773;
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 14px 0 6px 4px;
        }

        /* ---- Center hero / input ---- */
        .ae-hero {
            text-align: center;
            margin-top: 6vh;
            margin-bottom: 2rem;
        }
        .ae-hero h1 {
            font-size: 2.1rem;
            font-weight: 700;
            background: linear-gradient(90deg, #17b2a0, #4dd2ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.4rem;
        }
        .ae-hero p {
            color: #8b98a5;
            font-size: 0.95rem;
        }

        div[data-testid="stTextInput"] input {
            background-color: #161b22;
            border: 1px solid #2a3441;
            border-radius: 24px;
            padding: 0.85rem 1.2rem;
            color: #e6edf3;
            font-size: 1rem;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #17b2a0;
            box-shadow: 0 0 0 1px #17b2a0;
        }

        /* ---- Answer card ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #12161c;
            border: 1px solid #22272e !important;
            border-radius: 14px;
        }

        /* ---- Tabs ---- */
        button[data-baseweb="tab"] {
            color: #8b98a5;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #17b2a0;
        }

        h1, h2, h3 { color: #e6edf3; }
    </style>
    """,
    unsafe_allow_html=True,
)

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

if "pending_query" not in st.session_state:
    st.session_state.pending_query = ""

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
    # Compute query embedding
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
# Sidebar — ChatGPT-inspired layout (New Question button + Recents + Config)
# ============================================================================
with st.sidebar:
    st.markdown(
        "<h2 style='color:#17b2a0; margin-bottom:2px;'>⚡ AE Assistant</h2>",
        unsafe_allow_html=True,
    )
    st.caption("Product Q&A · powered by your document base")

    if st.button("➕  New Question"):
        st.session_state.pending_query = ""
        st.session_state.query_input = ""
        st.rerun()

    st.markdown("<div class='ae-section-label'>Recents</div>", unsafe_allow_html=True)

    if st.session_state.chat_history:
        for entry in reversed(st.session_state.chat_history[-12:]):
            label = entry["question"]
            if len(label) > 34:
                label = label[:34] + "…"
            st.markdown(f"<div class='ae-recent-item'>💬 {label}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='ae-recent-item'>No questions yet</div>", unsafe_allow_html=True
        )

    st.markdown("<div class='ae-section-label'>Configuration</div>", unsafe_allow_html=True)

    with st.expander("🔑 Gemini API Key", expanded=False):
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

    with st.expander("📊 Retrieval Settings", expanded=False):
        n_results = st.slider(
            "Documents to retrieve:",
            min_value=1,
            max_value=10,
            value=5,
            help="Higher values provide more context but may dilute relevance",
        )

    with st.expander("📚 Database Info", expanded=False):
        if st.session_state.db_loaded:
            st.success("✅ Database loaded")
        else:
            st.info("Loading database...")
        st.caption(f"**Location:** `{DB_DIR}`")
        st.caption(f"**Collection:** `{COLLECTION_NAME}`")
        st.caption("**Embeddings:** TF-IDF + SVD (128 dims)")
        st.caption("**Storage:** Persistent ChromaDB")

    with st.expander("💡 Tips", expanded=False):
        st.markdown(
            """
- **Ask specific questions**: "What high voltage power supplies do you offer?"
- **Search by category**: "Tell me about plasma power products"
- **Ask for specifications**: "What are DC-DC converters used for?"
- **Compare products**: "What's the difference between..."
            """
        )

    if st.session_state.chat_history:
        st.divider()
        if st.button("🗑️  Clear all history"):
            st.session_state.chat_history = []
            st.rerun()

# ============================================================================
# Main Content — centered hero + search-style input (only when no history)
# ============================================================================
if not st.session_state.chat_history:
    st.markdown(
        """
        <div class='ae-hero'>
            <h1>Ask about our products</h1>
            <p>Answers are generated only from Advanced Energy's product documentation.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================================
# Initialize Database
# ============================================================================
if not st.session_state.db_loaded:
    with st.spinner("🔄 Loading embedding model and database..."):
        try:
            ef = load_embedding_model(DB_DIR)
            if ef is None:
                st.error(
                    f"❌ Embedding model not found. Run `python embed_to_chroma.py` first."
                )
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
# Query Interface
# ============================================================================
query = st.text_input(
    "Ask anything about our products",
    placeholder="e.g., Do you have high voltage power supplies?",
    key="query_input",
    label_visibility="collapsed",
)

if query:
    with st.spinner("🤔 Thinking..."):
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

        except Exception as e:
            st.error(f"❌ Error processing question: {e}")
            st.stop()

# ============================================================================
# Display Results
# ============================================================================
if st.session_state.chat_history:
    latest = st.session_state.chat_history[-1]

    st.divider()
    st.subheader("💬 Answer")
    with st.container(border=True):
        st.markdown(latest["answer"])

    st.divider()
    st.subheader("📄 Retrieved Context")

    tabs = st.tabs([f"Source {i + 1}" for i in range(len(latest["context_blocks"]))])

    for tab, block in zip(tabs, latest["context_blocks"]):
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