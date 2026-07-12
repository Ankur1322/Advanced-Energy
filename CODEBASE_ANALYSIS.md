# Advanced Energy Products RAG Codebase Analysis

## 🎯 Project Overview

**Purpose:** A terminal-based Retrieval-Augmented Generation (RAG) system that scrapes Advanced Energy product information, embeds it into a vector database, and enables semantic Q&A using Google Gemini API.

**Core Workflow:** Scrape Products → Embed to ChromaDB → Query with RAG

---

## 📊 Architecture

```
scraper.py
    ↓ (creates)
products/ (filesystem hierarchy)
    ↓
embed_to_chroma.py
    ↓ (creates)
chroma_db/ (vector database)
    ↓
rag_chat.py (queries)
    ↓
Google Gemini API (LLM)
```

---

## 📁 File-by-File Analysis

### 1. **scraper.py** (Web Scraper)
**Purpose:** Crawls Advanced Energy website and builds a local filesystem hierarchy of product data.

**Key Responsibilities:**
- Fetches the main products page from `https://www.advancedenergy.com/en-us/products/`
- Extracts product categories and sub-products from HTML structure
- For each sub-product, fetches its dedicated page and extracts description
- Writes structured text files locally

**Important Classes/Functions:**
- `extract_categories(soup)` — Parses category cards and sub-product lists from HTML
- `extract_subproduct_description(soup)` — Extracts descriptions from individual product pages (tries meta description, then container divs, then first substantial `<p>`)
- `write_details()` — Creates `details.txt` for each sub-product
- `write_category_summary()` — Creates `category_summary.txt` listing all sub-products
- `build_tree_text()` — Generates ASCII tree visualization in `all_products_tree.txt`
- `fetch_page()` — HTTP GET with retry logic (3 attempts, exponential backoff)

**Key Features:**
- **Rate limiting:** Configurable delay between requests (default 0.5s, adjustable with `--delay`)
- **Filesystem safety:** Sanitizes folder names to remove illegal characters (`\/:*?"<>|`)
- **Resilient:** Retries failed HTTP requests up to 3 times
- **Verbose logging:** Optional debug mode with `--verbose` flag

**Data Output Structure:**
```
products/
├── Plasma Power Products/
│   ├── RF Plasma Generators/
│   │   └── details.txt
│   ├── RF Match Networks/
│   │   └── details.txt
│   └── category_summary.txt
├── AC-DC Power Supply Units/
│   ├── AC Input PCB Mount/
│   │   └── details.txt
│   └── category_summary.txt
└── all_products_tree.txt
```

**Sample details.txt:**
```
Subproduct Name: AC Input PCB Mount
Category: AC-DC Power Supply Units
Source Link: https://www.advancedenergy.com/en-us/products/ac-dc-power-supply-units/encapsulated-pcb-mount/
Description:
Best suited for applications requiring low-power solutions, our power factor correction (PFC) and AC-DC modules enable quick application design-ins.
```

**CLI Usage:**
```bash
python scraper.py                          # Default: outputs to ./products
python scraper.py --output my_data         # Custom output directory
python scraper.py --delay 1                # 1 second between requests
python scraper.py --verbose                # Debug logging
python scraper.py --output ae_data --delay 1 --verbose  # All options
```

---

### 2. **embed_to_chroma.py** (Embedding & Vector DB)
**Purpose:** Reads scraped product data, creates embeddings, and stores in ChromaDB vector database.

**Key Responsibilities:**
- Parses all `details.txt` and `category_summary.txt` files
- Creates TF-IDF + SVD embeddings (fully offline, no model downloads)
- Persists embeddings in ChromaDB for semantic search

**Important Classes/Functions:**
- `TfidfSvdEmbeddingFunction` — Custom embedding function
  - `fit(documents)` — Trains TF-IDF vectorizer + SVD projector on all documents
  - `__call__(input)` — Converts text to normalized embedding vectors (128 dims)
  - `save(path)` / `load(path)` — Serializes/deserializes model to disk
- `parse_details(path)` — Extracts structured fields from `details.txt` (regex-based parsing)
- `parse_category_summary(path)` — Parses category summary format
- `load_all_documents()` — Recursively loads all product documents
- `embed()` — Main orchestrator: trains embeddings, creates ChromaDB collection, batches documents

**Embedding Strategy:**
- **Algorithm:** TF-IDF (term frequency-inverse document frequency) with TruncatedSVD dimensionality reduction
- **Dimensions:** 128
- **Vectorizer Settings:**
  - max_features: 5,000 (top 5k terms)
  - stop_words: English (removes "the", "a", etc.)
  - ngram_range: (1, 2) (unigrams + bigrams)
  - sublinear_tf: True (applies sublinear term frequency scaling)
- **Normalization:** L2 normalization of reduced vectors

**ChromaDB Setup:**
- Persistent storage at `./chroma_db/`
- Collection name: `ae_products`
- Distance metric: Cosine similarity
- Metadata tracked: type (category_summary or subproduct_detail), category, subproduct, source_link

**Document Processing:**
Two document types are created:
1. **Category summaries** — One per category, lists all subproducts
   - ID: `cat_{slug(category_name)}`
   - Example: `cat_plasma_power_products`

2. **Subproduct details** — One per subproduct, contains full description + metadata
   - ID: `sub_{slug(category)}_{slug(subproduct)}`
   - Example: `sub_ac_dc_power_supply_units_ac_input_pcb_mount`

**CLI Usage:**
```bash
python embed_to_chroma.py                   # Uses default paths
python embed_to_chroma.py --products-dir products --db-dir chroma_db  # Custom paths
```

**Verification Output:**
Runs two sample queries at the end to verify embeddings work:
- "high voltage power supply"
- "plasma RF generator"

---

### 3. **rag_chat.py** (Q&A Chatbot)
**Purpose:** Interactive or CLI-based Q&A interface that retrieves relevant products and generates answers using Google Gemini.

**Key Responsibilities:**
- Loads ChromaDB collection and pre-trained embeddings
- Converts user queries to embeddings
- Retrieves top-K similar documents (default: 5)
- Constructs a prompt with retrieved context
- Sends to Gemini API for grounded, fact-based responses

**Important Classes/Functions:**
- `setup_gemini()` — Configures Gemini API; falls back to mock mode if key unavailable
- `get_llm_response_with_retry()` — Sends prompt to Gemini with rate-limiting retry logic
  - Tries multiple model variants: `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-pro-latest`, etc.
  - Handles 429 (rate limit) errors with exponential backoff
  - Falls back to offline mock mode if no API key configured
- `ask_question(query, db_dir, n_results=5)` — Orchestrates retrieval + LLM generation
- `main()` — CLI entry point supporting both single queries and interactive mode

**Prompt Engineering:**
Includes strict rules in the prompt to force Gemini to:
1. Only use information from retrieved context
2. Not use external knowledge or general training data
3. Refuse to answer if context insufficient
4. Always cite product names exactly as they appear
5. Point out contradictions rather than guess

**Retrieval Mechanism:**
- Loads the fitted `TfidfSvdEmbeddingFunction` from disk
- Embeds user query using same vectorizer/SVD as training
- Queries ChromaDB with cosine similarity
- Retrieves top-5 (configurable) matching documents with metadata

**Mock Mode:**
If `GEMINI_API_KEY` is not set:
- Formats retrieval results in a human-readable summary
- Shows category/subproduct matches
- Prompts user to set API key for full AI answers

**CLI Usage:**
```bash
# Single query mode
python rag_chat.py "Do they have high voltage power supplies?"

# Interactive mode
python rag_chat.py --interactive

# Custom database
python rag_chat.py --interactive --db-dir /path/to/chroma_db

# One-off query with custom retrieval count
python rag_chat.py "Query here" --n-results 10  # (if this arg were added)
```

**Example Interaction:**
```
Question: Do they have high voltage power supplies?
Thinking...

--- Context Source 1 (category_summary) ---
Category: High Voltage Power Supplies
Subproduct: High Power
Content: ...

Answer:
Yes, Advanced Energy offers High Voltage Power Supplies in the following categories:
- High Power systems
- Low Power systems
...
```

---

## 📦 Dependencies

```
requests>=2.28.0           # HTTP fetching (scraper)
beautifulsoup4>=4.11.0    # HTML parsing (scraper)
chromadb>=1.5.0           # Vector database (embedding + retrieval)
scikit-learn>=1.0.0       # TF-IDF, SVD embeddings
numpy>=1.22.5             # Numerical operations
google-generativeai>=0.8.0 # Gemini API client
```

---

## 🔄 Complete Workflow

### Step 1: Scraping
```bash
python scraper.py --output products --delay 0.5 --verbose
```
**Outcome:** `products/` directory with 100+ files organized by category

### Step 2: Embedding
```bash
python embed_to_chroma.py --products-dir products --db-dir chroma_db
```
**Outcome:**
- `chroma_db/embedding_model.pkl` — Fitted TF-IDF + SVD model
- `chroma_db/` — Persistent ChromaDB storage with ~50-100 embeddings

### Step 3: Q&A
```bash
export GEMINI_API_KEY="your_key_here"
python rag_chat.py --interactive
```
**Outcome:** Interactive prompt ready for product questions

---

## 📊 Data Structure Summary

### Category Breakdown
Currently scraped categories (7 total):
1. **AC-DC Power Supply Units** (14 subproducts)
2. **DC-DC Converters** (9 subproducts)
3. **High Voltage Amplifiers** (3 subproducts)
4. **High Voltage Power Supplies** (5 subproducts)
5. **Plasma Power Products** (6 subproducts)
6. **SCR Power Controllers** (2 subproducts)
7. **Sense and Measurement** (7 subproducts)

**Total:** ~46 sub-products across 7 categories

### Metadata Tracked
Per subproduct:
- Subproduct Name
- Category
- Source Link (URL)
- Description (extracted from product page)

Per category:
- Category Name
- Total Subproducts (count)
- List of Subproducts

---

## 🎯 Key Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Embedding** | TF-IDF + SVD | Fully offline, no model downloads, fast, no GPU needed |
| **Dimensions** | 128 | Good balance between speed and semantic quality |
| **Distance** | Cosine similarity | Standard for embedding-based retrieval |
| **LLM** | Google Gemini | Free tier available, multi-model fallback for reliability |
| **Fallback** | Mock mode | Allows testing without API key |
| **Storage** | Filesystem + ChromaDB | Simple, inspectable, persistent |
| **Rate Limit** | 0.5s delay | Polite to target website |

---

## ⚠️ Potential Issues & Improvements

### Current Limitations
1. **Static Data** — Requires manual re-scrape to update products; no incremental updates
2. **Description Quality** — Some products show "Not found" if page layout unusual
3. **Embedding Context Window** — TF-IDF loses word order; doesn't understand semantic relationships deeply
4. **Gemini Fallback Chain** — Multiple model attempts may be slow; no timeout
5. **No Caching** — Every query re-computes embeddings (minor cost)
6. **No Persistent Chat** — Each query is independent; no conversation history
7. **Single Language** — Only works with English content
8. **Manual Embedding Reload** — `rag_chat.py` loads model from disk every query (not cached in memory)

### Suggested Enhancements
1. **Incremental Scraper** — Only fetch new/changed products
2. **Better Embeddings** — Use pre-trained models (e.g., Sentence Transformers) for semantic understanding
3. **Streaming Responses** — Show Gemini responses as they generate
4. **Persistent Sessions** — Store conversation history + citations
5. **Web Interface** — Flask/FastAPI wrapper for browser access
6. **Scheduled Updates** — Cron/Airflow for automatic re-scraping
7. **Product Filtering** — Allow users to filter by category, specs, etc.
8. **Monitoring** — Track query success rates, latency, Gemini API costs
9. **Structured Output** — Return JSON with product links, specs, exact matches
10. **Multi-Turn Q&A** — Support follow-up questions with context carry-over

---

## 🧪 Testing the System

### Minimal Setup
```bash
# 1. Install
pip install -r requirements.txt

# 2. Scrape (takes ~5-10 min depending on rate limit)
python scraper.py

# 3. Embed
python embed_to_chroma.py

# 4. Test without API key (mock mode)
python rag_chat.py "What power supplies do you have?"

# 5. Test with API key (real Gemini)
export GEMINI_API_KEY="sk-..."
python rag_chat.py --interactive
```

### Example Queries to Try
- "Do you have plasma power products?"
- "What are DC-DC converters used for?"
- "List all high voltage amplifier types"
- "Tell me about RF plasma generators"
- "What power supplies do you recommend for IoT?"

---

## 📋 Summary

| Component | Role | Status |
|-----------|------|--------|
| **scraper.py** | Web scraper → filesystem | ✅ Complete, production-ready |
| **embed_to_chroma.py** | Embedding + vector DB | ✅ Complete, fully offline |
| **rag_chat.py** | Q&A chatbot | ✅ Complete, fallback mode works |
| **Data** | 46 subproducts across 7 categories | ✅ Fully populated |
| **Integration** | End-to-end pipeline | ✅ Functional |

**Overall Status:** 🟢 **Fully functional RAG system** ready for deployment or enhancement.
