#!/usr/bin/env python3
"""
Advanced Energy JSON API Bridge
================================
Runs a RAG search against ChromaDB and queries Google Gemini,
returning a clean, structured JSON response. Can be executed
from Node.js or any external client.
"""

import os
import sys
import json
import warnings
from pathlib import Path
from functools import lru_cache

warnings.filterwarnings("ignore")

import chromadb
import google.generativeai as genai
from embed_to_chroma import COLLECTION_NAME, DB_DIR, TfidfSvdEmbeddingFunction

@lru_cache(maxsize=1)
def load_retriever():
    """Load the expensive local embedding model and Chroma client once per worker."""
    db_dir = DB_DIR
    ef = TfidfSvdEmbeddingFunction.load(db_dir / "embedding_model.pkl")
    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    return collection


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)

    query = sys.argv[1].strip()
    try:
        history = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
        if not isinstance(history, list):
            history = []
    except (json.JSONDecodeError, TypeError):
        history = []

    # Check Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    using_mock = not api_key

    if api_key:
        try:
            getattr(genai, "configure")(api_key=api_key)
        except Exception as e:
            using_mock = True

    try:
        collection = load_retriever()
        results = collection.query(query_texts=[query], n_results=5)

        sources = []
        context_blocks = []
        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        for idx, (doc, meta) in enumerate(zip(documents, metadatas), 1):
            meta = meta or {}
            category = meta.get("category", "")
            subproduct = meta.get("subproduct", "")
            description = meta.get("description", "")
            url = meta.get("source_link", "Not found")
            image_url = meta.get("image_url", "Not found")

            sources.append({
                "id": idx,
                "category": category,
                "subproduct": subproduct,
                "description": description,
                "url": url,
                "image_url": image_url,
                "content": doc
            })

            block = f"--- Context Source {idx} ---\n"
            if category: block += f"Category: {category}\n"
            if subproduct: block += f"Subproduct: {subproduct}\n"
            block += f"Content:\n{doc}\n"
            context_blocks.append(block)

        context = "\n".join(context_blocks)

        if using_mock:
            # Generate structured mock response
            answer = "🤖 **[Offline Mock Mode Active]**\n\n"
            if not sources:
                answer += "No matching products were found in the local database.\n"
            answer += "Here are the most relevant matching products found in the Advanced Energy database:\n\n"
            for src in sources[:3]:
                answer += f"### {src['subproduct']}\n"
                answer += f"**Category:** {src['category']}\n\n"
                if src['description'] and src['description'] != "Not found":
                    answer += f"*{src['description']}*\n\n"
                if src['url'] and src['url'] != "Not found":
                    answer += f"[View Product Page]({src['url']})\n\n"
                answer += "---\n\n"
            answer += "\n*(To unlock real AI-generated conversational answers, please configure your `GEMINI_API_KEY` inside the sidebar settings!)*"
        else:
            prior_turns = "\n".join(
                f"{item.get('role', 'user').upper()}: {str(item.get('content', ''))[:1200]}"
                for item in history[-12:]
                if isinstance(item, dict) and item.get('content')
            )
            prompt = f"""You are an expert product assistant for Advanced Energy.
Use the following retrieved context and conversation history to answer the user's question.
Conversation history (may be empty):
{prior_turns}

Retrieved context:
If the retrieved context does not contain enough information to answer, answer with what you can, and be honest about missing details.
Always mention the specific product names and categories when answering.
Do not print raw image URLs in the answer. Product images are rendered separately by the dashboard.

{context}

USER QUESTION: {query}

ANSWER:"""
            # Choose a model
            models_to_try = [
                "models/gemini-2.5-flash",
                "models/gemini-2.0-flash",
                "models/gemini-pro-latest",
                "gemini-1.5-flash",
                "gemini-pro",
            ]
            answer = ""
            for model_name in models_to_try:
                try:
                    model = getattr(genai, "GenerativeModel")(model_name)
                    response = model.generate_content(prompt)
                    answer = response.text
                    break
                except Exception as e:
                    continue
            if not answer:
                raise Exception("Could not generate answer from any Gemini model.")

        print(json.dumps({
            "answer": answer,
            "sources": sources,
            "using_mock": using_mock
        }, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
