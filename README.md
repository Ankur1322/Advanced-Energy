# Advanced Energy - AE BOT & RAG Intelligence Dashboard

A full-stack Retrieval-Augmented Generation (RAG) system and interactive Node.js dashboard designed exclusively for the Advanced Energy products catalog.

This project maps the entire Advanced Energy product taxonomy into a local ChromaDB vector space and uses Google Gemini to answer questions with verifiable, cited product specifications and live images.

[![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?logo=render&logoColor=white)](https://dashboard.render.com)
[![Live App](https://img.shields.io/badge/Live_App-Open-0EA5E9)](https://advanced-energy-dashboard.onrender.com)
[![Documentation](https://img.shields.io/badge/Documentation-README-334155)](#system-architecture)
[![System Design Report](https://img.shields.io/badge/System_Design-Architecture-7C3AED)](#system-architecture)

**Live dashboard:** [advanced-energy-dashboard.onrender.com](https://advanced-energy-dashboard.onrender.com)

## System Architecture

The platform combines a local product-ingestion and retrieval pipeline with a Node.js dashboard:

The project is split into three main components:

### 1. Ingestion Engine (`scraper.py`)

A terminal-only Python scraper that reads the [Advanced Energy products page](https://www.advancedenergy.com/en-us/products/).

- Crawls categories, sub-products, and extracts descriptions, features, and product images (via `og:image` and `twitter:image`).
- Builds a filesystem hierarchy of `product_details.txt` files inside the `output/` directory.

### 2. Vectorization Pipeline (`embed_to_chroma.py`)

Parses the scraped text files and builds a local vector database.

- Uses a **fully offline TF-IDF + Truncated SVD model** to project product specs into a 128-dimensional dense vector space.
- Stores vectors and metadata (including image URLs) in a local SQLite-backed `ChromaDB`.

### 3. Node.js Dashboard & AI Chat (`dashboard/` & `query_api.py`)

A modern, highly-polished Express backend and GSAP-animated frontend.

- Connects the React-style HTML frontend to the Python RAG system via the `query_api.py` JSON bridge.
- **AE BOT**: A conversational AI interface that takes user questions, queries ChromaDB for the Top-5 most relevant product specs, and passes them to Google Gemini for synthesis.
- Renders rich product citations with embedded images, direct datasheet links, and fully parsed markdown.

---

## Installation & Setup

### 1. Python Environment (Scraper & AI Backend)

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Node.js Environment (Dashboard UI)

```bash
# Navigate to the dashboard directory
cd dashboard

# Install Node.js dependencies (Express, CORS, dotenv)
npm install
```

### 3. Memory Chat App

The `memory-app/` directory contains the Supabase-backed chat history and long-term memory UI.

```bash
cd memory-app
npm install
cp .env.example .env.local
# Edit .env.local with your Supabase project URL and anon key
npm run dev
```

The Vite app will be available at the local URL printed in the terminal. The database migration is at `memory-app/supabase/migrations/202610050001_long_term_memory.sql`; apply it to the Supabase project before using conversations, messages, or memory retrieval.

For a production build, run `npm run typecheck && npm run build` from `memory-app`.

---

## Usage Guide

### Step 1: Scrape the Product Data

Before the bot can answer questions, it needs data. Run the scraper from the root directory:

```bash
python scraper.py --output output
```

*(This creates the `output/Products` folder containing all parsed text sheets.)*

### Step 2: Build the Vector Database

Convert the text sheets into searchable vector chunks:

```bash
python embed_to_chroma.py
```

*(This generates the `chroma_db/` folder and `embedding_model.pkl`.)*

### Step 3: Launch the Dashboard

Start the Node.js Express server to host the UI:

```bash
cd dashboard
node server.js
```

The application will be live at: **http://localhost:3000**

The production dashboard is available at [advanced-energy-dashboard.onrender.com](https://advanced-energy-dashboard.onrender.com).

### Production deployment

The included `dashboard/Dockerfile` packages the Node dashboard and Python RAG engine. Build from the repository root:

```bash
docker build -f dashboard/Dockerfile -t advanced-energy-bot .
docker run --rm -p 3000:3000 \
  -e GEMINI_API_KEY=your_api_key_here \
  -v advanced-energy-memory:/app/data \
  advanced-energy-bot
```

Set `PORT`, `PYTHON_PATH`, `QUERY_TIMEOUT_MS`, and `MAX_MEMORY_TURNS` as needed. Keep `GEMINI_API_KEY` server-side in production; the browser key field is retained only for local testing. The `/app/data` volume preserves conversations across restarts.

### Conversation memory

Each browser gets a stable conversation ID in `localStorage`. The server stores at most `MAX_MEMORY_TURNS` turns per conversation (20 by default), truncates individual messages to 4,000 characters, and sends only the last 12 turns to Gemini. This keeps prompt size and memory usage bounded while preserving recent context. To reset a browser conversation, clear the `ae_bot_conversation_id` local-storage item.

### Step 4: Configure the Bot

1. Open the dashboard in your browser.
2. Click the Settings / Gear icon or navigate to the **Configure** tab.
3. Paste your **Google Gemini API Key**.
4. The engine will instantly unlock from "Mock Mode" to "Active Mode", enabling real-time generative AI answers.

---

## Technical Details

- **Responsive GSAP UI**: The frontend utilizes Three.js for an interactive, watery particle mesh background and GSAP for buttery smooth nested-sidebar transitions.
- **Offline Embeddings**: To ensure blistering fast retrieval speeds (sub-5ms) and zero external embedding costs, we developed a local TF-IDF+SVD model instead of calling expensive OpenAI/Vertex embeddings.
- **Null-Safe Event Hooks**: The JS UI is fully modularized and gracefully degrades if specific DOM elements are hidden or collapsed.
