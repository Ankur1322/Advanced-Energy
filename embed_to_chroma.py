#!/usr/bin/env python3
"""
Advanced Energy Products → ChromaDB Embedder
=============================================
Reads the recursively scraped product hierarchy under output/ (every
leaf folder containing a single product_details.txt) and creates vector
embeddings in a persistent ChromaDB collection.
"""

import argparse
import hashlib
import re
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

warnings.filterwarnings("ignore")

import chromadb
import chromadb.errors
import numpy as np
from chromadb.api.types import EmbeddingFunction
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer


PRODUCTS_DIR = Path("output")
DB_DIR = Path("chroma_db")
COLLECTION_NAME = "ae_products"
EMBEDDING_DIM = 128

LIST_HEADER_RE = re.compile(
    r"^(Features|Specifications|Applications|Benefits|Downloads|PDF Links|Images|Related Products):\s*(.*)$"
)
FIELD_KEY_MAP = {
    "Features": "features",
    "Specifications": "specifications",
    "Applications": "applications",
    "Benefits": "benefits",
    "Downloads": "downloads",
    "PDF Links": "pdf_links",
    "Images": "images",
    "Related Products": "related_products",
}
PAIR_FIELDS = {"downloads", "images", "related_products"}


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


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_")[:60]


def _doc_id(prefix: str, parts: List[str]) -> str:
    readable = "_".join(_slug(p) for p in parts)[:80]
    full_path = "|".join(parts)
    digest = hashlib.sha1(full_path.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{readable}_{digest}"


def parse_product_details(text: str) -> dict:
    data = {
        "hierarchy": [], "product_name": "", "product_url": "",
        "description": "Not found", "features": [], "specifications": [],
        "applications": [], "benefits": [], "downloads": [], "pdf_links": [],
        "images": [], "related_products": [], "breadcrumb": [],
    }
    section = None
    current_cat = None
    current_list_key = None
    collecting_description = False
    description_lines: List[str] = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()

        if stripped == "HIERARCHY (root to product, chronological order)":
            section = "hierarchy"
            continue
        if stripped.startswith("FINAL PRODUCT"):
            section = "product"
            continue
        if stripped == "NAVIGATION PATH (Breadcrumb)":
            if collecting_description:
                data["description"] = " ".join(description_lines).strip() or "Not found"
                collecting_description = False
                description_lines = []
            section = "breadcrumb"
            continue
        if stripped.startswith("---") or stripped.startswith("==="):
            continue

        if section == "hierarchy":
            m = re.match(r"^\[Level (\d+)\] Category Name:\s*(.*)", stripped)
            if m:
                current_cat = {"level": int(m.group(1)), "name": m.group(2).strip(), "url": "", "description": ""}
                data["hierarchy"].append(current_cat)
            elif stripped.startswith("Category URL:") and current_cat is not None:
                current_cat["url"] = stripped.split("Category URL:", 1)[1].strip()
            elif stripped.startswith("Category Description:") and current_cat is not None:
                current_cat["description"] = stripped.split("Category Description:", 1)[1].strip()
            elif stripped and current_cat is not None and not stripped.startswith("["):
                current_cat["description"] = (current_cat["description"] + " " + stripped).strip()

        elif section == "product":
            list_match = LIST_HEADER_RE.match(stripped)
            if stripped.startswith("Product Name:"):
                data["product_name"] = stripped.split("Product Name:", 1)[1].strip()
            elif stripped.startswith("Product URL:"):
                data["product_url"] = stripped.split("Product URL:", 1)[1].strip()
            elif stripped == "Complete Product Description:":
                collecting_description = True
                description_lines = []
                current_list_key = None
            elif list_match:
                if collecting_description:
                    data["description"] = " ".join(description_lines).strip() or "Not found"
                    collecting_description = False
                    description_lines = []
                title, rest = list_match.group(1), list_match.group(2).strip()
                key = FIELD_KEY_MAP[title]
                current_list_key = None if rest.lower() == "not found" else key
            elif current_list_key and stripped.startswith("- "):
                item = stripped[2:].strip()
                if item:
                    if current_list_key in PAIR_FIELDS and ": " in item:
                        label, _, url = item.partition(": ")
                        data[current_list_key].append((label.strip(), url.strip()))
                    elif current_list_key in PAIR_FIELDS:
                        data[current_list_key].append((item, ""))
                    else:
                        data[current_list_key].append(item)
            elif collecting_description and stripped:
                description_lines.append(stripped)

        elif section == "breadcrumb":
            if stripped and stripped != "\u2193":
                data["breadcrumb"].append(stripped)

    if collecting_description and description_lines:
        data["description"] = " ".join(description_lines).strip()

    return data


def load_all_documents(products_dir: Path) -> Tuple[list, list]:
    sub_docs = []
    category_map: Dict[Tuple[str, ...], dict] = {}

    detail_files = sorted(products_dir.rglob("product_details.txt"))
    for path in detail_files:
        text = path.read_text(encoding="utf-8")
        info = parse_product_details(text)

        product_name = info["product_name"] or path.parent.name
        hierarchy = info["hierarchy"]
        breadcrumb_names = [h["name"] for h in hierarchy]
        category_path_str = " > ".join(breadcrumb_names) if breadcrumb_names else "Unknown"
        top_category = (
            hierarchy[1]["name"] if len(hierarchy) > 1
            else (hierarchy[0]["name"] if hierarchy else "Uncategorized")
        )

        doc_text_parts = [
            f"Product Name: {product_name}",
            f"Category Path: {category_path_str}",
            f"Product URL: {info['product_url'] or 'Not found'}",
            f"Description: {info['description']}",
        ]
        if info["features"]:
            doc_text_parts.append("Features: " + "; ".join(info["features"]))
        if info["specifications"]:
            doc_text_parts.append("Specifications: " + "; ".join(info["specifications"]))
        if info["applications"]:
            doc_text_parts.append("Applications: " + "; ".join(info["applications"]))
        if info["benefits"]:
            doc_text_parts.append("Benefits: " + "; ".join(info["benefits"]))
        if info["related_products"]:
            related_names = "; ".join(name for name, _ in info["related_products"] if name)
            if related_names:
                doc_text_parts.append("Related Products: " + related_names)

        doc_text = "\n".join(doc_text_parts)
        rel_parts = list(path.relative_to(products_dir).parts[:-1])
        doc_id = _doc_id("product", rel_parts)

        primary_img = "Not found"
        if info["images"]:
            first_img = info["images"][0]
            primary_img = first_img[1] if isinstance(first_img, (list, tuple)) and len(first_img) > 1 else (first_img[0] if isinstance(first_img, (list, tuple)) else str(first_img))

        sub_docs.append({
            "id": doc_id,
            "text": doc_text,
            "metadata": {
                "type": "product_detail",
                "category": top_category,
                "category_path": category_path_str,
                "subproduct": product_name,
                "source_link": info["product_url"] or "Not found",
                "image_url": primary_img or "Not found",
                "level": hierarchy[-1]["level"] + 1 if hierarchy else 0,
            },
        })

        path_key: Tuple[str, ...] = ()
        for cat in hierarchy:
            path_key = path_key + (cat["name"],)
            entry = category_map.setdefault(path_key, {
                "name": cat["name"], "description": "", "url": cat.get("url", ""),
                "level": cat["level"], "products": set(),
            })
            if not entry["description"] and cat.get("description") and cat["description"] != "Not found":
                entry["description"] = cat["description"]
            entry["products"].add(product_name)

    cat_docs = []
    for path_key, entry in category_map.items():
        products_list = "; ".join(sorted(entry["products"]))
        doc_text = (
            f"Category: {entry['name']}\n"
            f"Category Path: {' > '.join(path_key)}\n"
            f"Description: {entry['description'] or 'Not found'}\n"
            f"Total Products: {len(entry['products'])}\n"
            f"Products: {products_list}"
        )
        cat_docs.append({
            "id": _doc_id("cat", list(path_key)),
            "text": doc_text,
            "metadata": {
                "type": "category_summary",
                "category": entry["name"],
                "category_path": " > ".join(path_key),
                "level": entry["level"],
            },
        })

    return sub_docs, cat_docs


def embed(products_dir: Path, db_dir: Path) -> None:
    print(f"Scanning {products_dir} for product_details.txt files (any depth) ...")
    sub_docs, cat_docs = load_all_documents(products_dir)
    all_docs = cat_docs + sub_docs
    print(f"  -> {len(cat_docs)} category summaries, {len(sub_docs)} product details = {len(all_docs)} total")

    if not all_docs:
        print("No documents found. Nothing to embed.")
        sys.exit(1)

    all_ids = [d["id"] for d in all_docs]
    if len(all_ids) != len(set(all_ids)):
        seen, dupes = set(), set()
        for _id in all_ids:
            if _id in seen:
                dupes.add(_id)
            seen.add(_id)
        print(f"ERROR: {len(dupes)} duplicate document IDs detected before insert:")
        for d in list(dupes)[:10]:
            print(f"  - {d}")
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
    except (ValueError, chromadb.errors.NotFoundError):
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
