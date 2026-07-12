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

## Notes

- **Missing descriptions**: If the scraper cannot extract a description from a sub-product page (e.g. the page uses an unusual layout or requires JavaScript), it writes `Not found` in the description field. The folder and other fields are still created.
- **Missing links**: If a sub-product has no dedicated page link, the source link field will read `Not found` and the scraper will not attempt a page fetch — the folder and a `details.txt` are still created with whatever data is available.
- **Rate limiting**: The script waits `--delay` seconds between sub-product page requests (default 0.5 s) to avoid overwhelming the server.
- **Retries**: HTTP requests are retried up to 3 times with exponential backoff on transient failures.
- **Folder names**: All filesystem-incompatible characters are automatically sanitised (e.g. `\/:*?"<>|` → `-`).

## Dependencies

- **requests** — HTTP fetching
- **beautifulsoup4** — HTML parsing
- **pathlib** — cross-platform filesystem paths (stdlib)
- **argparse** — CLI flag handling (stdlib)
