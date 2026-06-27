#!/usr/bin/env python3
"""
Advanced Energy Products → ChromaDB Embedder
=============================================
Reads the scraped product hierarchy under products/ and creates
vector embeddings in a persistent ChromaDB collection.

Uses TF-IDF + SVD (scikit-learn) for fully offline embeddings
with no model download required.

Two document types are embedded:
  1. Sub-product details  (from each details.txt)
  2. Category summaries   (from each category_summary.txt)

Usage:
    python embed_to_chroma.py
    python embed_to_chroma.py --products-dir products --db-dir chroma_db
"""

import argparse
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import chromadb
import numpy as np
from chromadb.api.types import EmbeddingFunction
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer


PRODUCTS_DIR = Path("products")
DB_DIR = Path("chroma_db")
COLLECTION_NAME = "ae_products"
EMBEDDING_DIM = 128


class TfidfSvdEmbeddingFunction(EmbeddingFunction):
    """Embedding function using TF-IDF + SVD (fully offline, no downloads)."""

    def __init__(self, dim: int = EMBEDDING_DIM):
        self._dim = dim
        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._svd = TruncatedSVD(n_components=dim, random_state=42)
        self._fitted = False

    def fit(self, documents: list[str]) -> None:
        tfidf_matrix = self._vectorizer.fit_transform(documents)
        self._svd.fit(tfidf_matrix)
        self._fitted = True

    def __call__(self, input: list[str]) -> list[list[float]]:
        if not self._fitted:
            raise RuntimeError("Call fit() before using the embedding function")
        tfidf_matrix = self._vectorizer.transform(input)
        reduced = self._svd.transform(tfidf_matrix)
        norms = np.linalg.norm(reduced, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = reduced / norms
        return normalized.tolist()

    def save(self, path: Path) -> None:
        import pickle
        data = {
            "vectorizer": self._vectorizer,
            "svd": self._svd,
            "dim": self._dim,
            "fitted": self._fitted,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps(data))

    @classmethod
    def load(cls, path: Path) -> "TfidfSvdEmbeddingFunction":
        import pickle
        data = pickle.loads(path.read_bytes())
        ef = cls(dim=data["dim"])
        ef._vectorizer = data["vectorizer"]
        ef._svd = data["svd"]
        ef._fitted = data["fitted"]
        return ef


def parse_details(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^([A-Za-z ]+):\s*(.*)", line)
        if m:
            if current_key:
                fields[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1).strip()
            current_lines = [m.group(2).strip()]
        else:
            current_lines.append(line)

    if current_key:
        fields[current_key] = "\n".join(current_lines).strip()

    return fields


def parse_category_summary(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}

    for line in text.splitlines():
        m = re.match(r"^(Category|Total Subproducts):\s*(.*)", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()

    subproducts = []
    for line in text.splitlines():
        m = re.match(r"^\d+\.\s+(.+)", line)
        if m:
            subproducts.append(m.group(1).strip())

    if subproducts:
        fields["Subproducts List"] = "; ".join(subproducts)

    return fields


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_")[:120]


def load_all_documents(products_dir: Path):
    sub_docs = []
    cat_docs = []

    for category_dir in sorted(products_dir.iterdir()):
        if not category_dir.is_dir():
            continue

        summary_path = category_dir / "category_summary.txt"
        if summary_path.exists():
            cat_fields = parse_category_summary(summary_path)
            cat_name = cat_fields.get("Category", category_dir.name)
            doc_text = (
                f"Category: {cat_name}\n"
                f"Total Subproducts: {cat_fields.get('Total Subproducts', 'N/A')}\n"
                f"Subproducts: {cat_fields.get('Subproducts List', 'N/A')}"
            )
            cat_docs.append({
                "id": f"cat_{_slug(cat_name)}",
                "text": doc_text,
                "metadata": {
                    "type": "category_summary",
                    "category": cat_name,
                },
            })

        for sub_dir in sorted(category_dir.iterdir()):
            if not sub_dir.is_dir():
                continue

            details_path = sub_dir / "details.txt"
            if not details_path.exists():
                continue

            fields = parse_details(details_path)
            sub_name = fields.get("Subproduct Name", sub_dir.name)
            cat_name = fields.get("Category", category_dir.name)
            description = fields.get("Description", "Not found")
            source_link = fields.get("Source Link", "Not found")

            doc_text = (
                f"Subproduct Name: {sub_name}\n"
                f"Category: {cat_name}\n"
                f"Source Link: {source_link}\n"
                f"Description: {description}"
            )

            sub_docs.append({
                "id": f"sub_{_slug(cat_name)}_{_slug(sub_name)}",
                "text": doc_text,
                "metadata": {
                    "type": "subproduct_detail",
                    "category": cat_name,
                    "subproduct": sub_name,
                    "source_link": source_link,
                },
            })

    return sub_docs, cat_docs


def embed(products_dir: Path, db_dir: Path) -> None:
    print(f"Loading documents from {products_dir} ...")
    sub_docs, cat_docs = load_all_documents(products_dir)
    all_docs = cat_docs + sub_docs
    print(f"  -> {len(cat_docs)} category summaries, {len(sub_docs)} sub-product details = {len(all_docs)} total")

    if not all_docs:
        print("No documents found. Nothing to embed.")
        sys.exit(1)

    print(f"Fitting TF-IDF + SVD embedding function ({EMBEDDING_DIM} dimensions) ...")
    ef = TfidfSvdEmbeddingFunction(dim=EMBEDDING_DIM)
    ef.fit([d["text"] for d in all_docs])

    model_path = db_dir / "embedding_model.pkl"
    db_dir.mkdir(parents=True, exist_ok=True)
    ef.save(model_path)
    print(f"  -> Saved embedding model to {model_path}")

    print(f"Initialising ChromaDB at {db_dir} ...")
    client = chromadb.PersistentClient(path=str(db_dir))

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  -> Deleted old collection (dimension mismatch possible)")
    except Exception:
        pass

    print(f"Creating collection '{COLLECTION_NAME}' ...")
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=ef,
    )

    print(f"  -> Adding {len(all_docs)} documents ...")
    batch_size = 50
    for i in range(0, len(all_docs), batch_size):
        batch = all_docs[i : i + batch_size]
        ids = [d["id"] for d in batch]
        docs = [d["text"] for d in batch]
        metas = [d["metadata"] for d in batch]
        collection.add(ids=ids, documents=docs, metadatas=metas)
        print(f"  -> Embedded batch {i // batch_size + 1}/{(len(all_docs) - 1) // batch_size + 1}")

    count = collection.count()
    print(f"\nDone. Collection '{COLLECTION_NAME}' now has {count} documents.")

    print("\n--- Quick verification: top 3 results for 'high voltage power supply' ---")
    results = collection.query(query_texts=["high voltage power supply"], n_results=3)
    for idx, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        print(f"\n  {idx}. [{meta.get('type')}] {meta.get('category', '')} / {meta.get('subproduct', '')}")
        preview = doc[:200].replace("\n", " ")
        print(f"     {preview}...")

    print("\n--- Quick verification: top 3 results for 'plasma RF generator' ---")
    results2 = collection.query(query_texts=["plasma RF generator"], n_results=3)
    for idx, (doc, meta) in enumerate(zip(results2["documents"][0], results2["metadatas"][0]), 1):
        print(f"\n  {idx}. [{meta.get('type')}] {meta.get('category', '')} / {meta.get('subproduct', '')}")
        preview = doc[:200].replace("\n", " ")
        print(f"     {preview}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed Advanced Energy products into ChromaDB (TF-IDF + SVD).")
    parser.add_argument("--products-dir", type=Path, default=PRODUCTS_DIR)
    parser.add_argument("--db-dir", type=Path, default=DB_DIR)
    args = parser.parse_args()

    if not args.products_dir.exists():
        print(f"Products directory not found: {args.products_dir}")
        sys.exit(1)

    embed(args.products_dir, args.db_dir)


if __name__ == "__main__":
    main()
