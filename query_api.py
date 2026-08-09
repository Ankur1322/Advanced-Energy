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

warnings.filterwarnings("ignore")

import chromadb
import google.generativeai as genai
from embed_to_chroma import COLLECTION_NAME, DB_DIR, TfidfSvdEmbeddingFunction

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)
        
    query = sys.argv[1]
    
    # Check Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    using_mock = not api_key
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            using_mock = True

    try:
        db_dir = DB_DIR
        ef = TfidfSvdEmbeddingFunction.load(db_dir / "embedding_model.pkl")
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
        )
        
        results = collection.query(query_texts=[query], n_results=5)
        
        sources = []
        context_blocks = []
        for idx, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
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
            if image_url and image_url != "Not found": block += f"Image URL: {image_url}\n"
            block += f"Content:\n{doc}\n"
            context_blocks.append(block)
            
        context = "\n".join(context_blocks)
        
        if using_mock:
            # Generate structured mock response
            answer = "🤖 **[Offline Mock Mode Active]**\n\n"
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
            prompt = f"""You are an expert product assistant for Advanced Energy.
Use the following retrieved context to answer the user's question.
If the retrieved context does not contain enough information to answer, answer with what you can, and be honest about missing details.
Always mention the specific product names and categories when answering.

CONTEXT:
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
                    model = genai.GenerativeModel(model_name)
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
