# Advanced Energy Products Scraper

Terminal-only Python scraper that reads the [Advanced Energy products page](https://www.advancedenergy.com/en-us/products/), extracts all product categories and sub-products, and builds a real filesystem hierarchy of `.txt` files.

## Output structure

```
products/
├── Plasma Power Products/
│   ├── RF Plasma Generators/
│   │   └── details.txt
│   ├── RF Match Networks/
│   │   └── details.txt
│   ├── Power Delivery Systems/
│   │   └── details.txt
│   ├── Pulsed and DC Power Systems/
│   │   └── details.txt
│   ├── Integrated Systems/
│   │   └── details.txt
│   ├── Remote Plasma Sources/
│   │   └── details.txt
│   └── category_summary.txt
├── AC-DC Power Supply Units/
│   ├── Bulk Power Shelves and Systems/
│   │   └── details.txt
│   ├── … (14 sub-products total)
│   └── category_summary.txt
├── DC-DC Converters/
│   ├── …
│   └── category_summary.txt
├── High Voltage Amplifiers/
│   ├── …
│   └── category_summary.txt
├── High Voltage Power Supplies/
│   ├── …
│   └── category_summary.txt
├── SCR Power Controllers/
│   ├── …
│   └── category_summary.txt
├── Sense and Measurement/
│   ├── …
│   └── category_summary.txt
├── Modified Standard and Custom Power Solutions/
│   ├── …
│   └── category_summary.txt
└── all_products_tree.txt
```

## Install

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

# 2. Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Default run — saves output to ./products
python scraper.py

# Custom output directory
python scraper.py --output my_data

# Increase delay between sub-product page fetches (seconds)
python scraper.py --delay 2

# Verbose logging (shows every URL fetched)
python scraper.py --verbose

# Combine flags
python scraper.py --output ae_data --delay 1 --verbose
```

### Full RAG Workflow

**Step 1: Scrape products**
```bash
python scraper.py --output products --delay 0.5
```

**Step 2: Embed to ChromaDB**
```bash
python embed_to_chroma.py --products-dir products --db-dir chroma_db
```

**Step 3: Run CLI chatbot**
```bash
export GEMINI_API_KEY="your_api_key_here"  # Optional
python rag_chat.py --interactive
```

**Step 3 (Alternative): Run Streamlit web UI** ⭐
```bash
export GEMINI_API_KEY="your_api_key_here"  # Optional
streamlit run streamlit_app.py
```

The Streamlit app provides:
- 🎨 **Beautiful web interface** for asking questions
- 💬 **Chat history** with all previous questions and answers
- 📄 **Retrieved context viewer** showing document sources
- ⚙️ **Configurable settings** (API key, retrieval count)
- 🤖 **Mock mode** for testing without API key

## Notes


## Dependencies

- **requests** — HTTP fetching
- **beautifulsoup4** — HTML parsing
- **pathlib** — cross-platform filesystem paths (stdlib)
- **argparse** — CLI flag handling (stdlib)
