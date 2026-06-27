#!/usr/bin/env python3
"""
Advanced Energy Products Q&A Bot (RAG)
=====================================
Queries ChromaDB to retrieve relevant product info, then uses Google Gemini
to answer questions. If GEMINI_API_KEY is not set, runs in a local mock mode
so you can still test it!

Prerequisites:
    export GEMINI_API_KEY="your_api_key_here"

Usage:
    python rag_chat.py "Do they have high voltage power supplies?"
    python rag_chat.py --interactive
"""

import os
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"

import argparse
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", message=".*unauthenticated.*")
warnings.filterwarnings("ignore", category=FutureWarning)

import chromadb
import google.generativeai as genai
from embed_to_chroma import COLLECTION_NAME, DB_DIR, SentenceTransformerEmbeddingFunction


USING_MOCK = False


def setup_gemini():
    global USING_MOCK
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        if sys.stdin.isatty():
            print("=" * 65)
            print("  Paste your Gemini API key below to enable full AI answers.")
            print("   (Or just press Enter to run in offline Mock Mode!)")
            print("=" * 65)
            entered_key = input("API Key: ").strip()
            if entered_key:
                api_key = entered_key
                os.environ["GEMINI_API_KEY"] = api_key
        if not api_key:
            USING_MOCK = True
            print("\n[Running in Offline/Mock Mode for testing!]")
            print("-" * 65)
            return

    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Failed to configure Gemini API: {e}. Falling back to Mock Mode.")
        USING_MOCK = True


def get_llm_response_with_retry(prompt: str, context: str, query: str, retries: int = 3, delay: int = 5) -> str:
    """Send prompt to Gemini with exponential backoff for 429 errors."""
    if USING_MOCK:
        response = (
            f"🤖 [Offline/Mock Assistant Response]\n"
            f"Here is the most relevant matching information found in our database for your question:\n\n"
        )
        lines = context.splitlines()
        found_any = False
        for line in lines:
            if any(term in line.lower() for term in ("subproduct:", "category:", "description:", "total subproducts:")) or "Category:" in line:
                response += f"• {line}\n"
                found_any = True
        if not found_any:
            response += f"Matches found:\n{context[:300]}..."
        response += f"\n(To get a fully natural AI answer, set your GEMINI_API_KEY environment variable!)"
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
                    print(f"  [Rate limited (429). Retrying in {delay}s... (Attempt {attempt}/{retries})]")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise e
    raise Exception("Could not find a supported Gemini model or exceeded retries.")


def ask_question(query: str, db_dir: Path, n_results: int = 5) -> str:
    ef = SentenceTransformerEmbeddingFunction()

    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
    )

    results = collection.query(query_texts=[query], n_results=n_results)

    context_blocks = []
    for idx, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        type_str = meta.get("type", "unknown")
        category = meta.get("category", "")
        subproduct = meta.get("subproduct", "")
        block = f"--- Context Source {idx} ({type_str}) ---\n"
        if category:
            block += f"Category: {category}\n"
        if subproduct:
            block += f"Subproduct: {subproduct}\n"
        block += f"Content:\n{doc}\n"
        context_blocks.append(block)

    context = "\n".join(context_blocks)

    prompt = f"""You are an expert product assistant for Advanced Energy.
Use the following retrieved context to answer the user's question.
If the retrieved context does not contain enough information to answer, answer with what you can, and be honest about missing details.
Always mention the specific product names and categories when answering.

CONTEXT:
{context}

USER QUESTION: {query}

ANSWER:"""

    return get_llm_response_with_retry(prompt, context, query)


def main():
    parser = argparse.ArgumentParser(description="Advanced Energy RAG Q&A Chatbot")
    parser.add_argument("query", nargs="?", help="The question to ask")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive CLI mode")
    parser.add_argument("--db-dir", type=Path, default=DB_DIR, help="Path to Chroma DB directory")
    args = parser.parse_args()

    setup_gemini()

    if args.interactive:
        print("=" * 60)
        print("  Advanced Energy Product Q&A Bot (Type 'exit' to quit)")
        print("=" * 60)
        while True:
            try:
                user_query = input("\nAsk a question: ").strip()
                if not user_query:
                    continue
                if user_query.lower() in ("exit", "quit"):
                    break
                print("\nThinking...")
                ans = ask_question(user_query, args.db_dir)
                print(f"\n{ans}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
    elif args.query:
        print(f"Question: {args.query}")
        print("Thinking...")
        try:
            ans = ask_question(args.query, args.db_dir)
            print(f"\nAnswer:\n{ans}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
