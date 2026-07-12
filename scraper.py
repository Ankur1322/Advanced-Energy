#!/usr/bin/env python3
"""
Advanced Energy Products Scraper
================================
Terminal-only Python scraper that reads the Advanced Energy products page,
builds a real filesystem hierarchy of categories > sub-products > details.txt,
plus category_summary.txt files and a root-level all_products_tree.txt.

CLI:
    python scraper.py
    python scraper.py --output products --delay 1 --verbose
"""

import argparse
import logging
import re
import sys
import textwrap
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://www.advancedenergy.com"
PRODUCTS_URL = f"{BASE_URL}/en-us/products/"
DEFAULT_OUTPUT = "products"
DEFAULT_DELAY = 0.5  # seconds between requests to be polite
REQUEST_TIMEOUT = 30  # seconds
USER_AGENT = (
    "Mozilla/5.0 (compatible; AE-ProductScraper/1.0; "
    "+https://github.com/example/ae-scraper)"
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG = logging.getLogger("ae_scraper")


def setup_logging(verbose: bool) -> None:
    """Configure terminal-only logging."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(message)s" if not verbose else "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)


# ---------------------------------------------------------------------------
# Slug / filename helpers
# ---------------------------------------------------------------------------
def sanitise(name: str) -> str:
    r"""Turn a category or sub-product name into a safe directory/file name.

    Steps:
    * Collapse whitespace.
    * Remove characters illegal on Windows and problematic on Linux
      (\/:*?"<>| replaced with dashes).
    * Strip leading/trailing dots and spaces.
    * Fall back to 'unnamed' if the result is empty.
    """
    if not name or not name.strip():
        return "unnamed"

    # Normalise whitespace
    safe = re.sub(r"\s+", " ", name).strip()

    # Replace forbidden filesystem characters
    safe = re.sub(r'[\\/:*?"<>|]', "-", safe)

    # Strip dots/spaces from edges (Windows Explorer restriction)
    safe = safe.strip(". ")

    return safe or "unnamed"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def fetch_page(url: str, session: requests.Session, retries: int = 3) -> Optional[BeautifulSoup]:
    """GET *url*, retry on transient failures, return parsed HTML or None."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as exc:
            LOG.warning("Request %d/%d failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    LOG.error("All %d retries exhausted for %s", retries, url)
    return None


# ---------------------------------------------------------------------------
# Extraction logic
# ---------------------------------------------------------------------------
def extract_categories(soup: BeautifulSoup) -> list[dict]:
    """Parse the products landing page and return a list of category dicts.

    Each dict has:
        name        – e.g. "Plasma Power Products"
        url         – full URL of the category page (or empty string)
        description – short intro text
        subproducts – list of dicts with 'name' and 'url'
    """
    categories: list[dict] = []

    # The page layout wraps each category card inside an <a> that points to
    # the category page, immediately followed by a <ul> with sub-products.
    # We iterate over every <a> that contains an <h3> (the category heading)
    # and then look at the next sibling <ul> for its <li><a> children.

    for heading in soup.find_all("h3"):
        parent_a = heading.find_parent("a")
        if not parent_a:
            continue

        cat_url = parent_a.get("href", "")
        cat_url = urljoin(BASE_URL, cat_url) if cat_url else ""

        cat_name = heading.get_text(strip=True)
        if not cat_name:
            continue

        # Try to grab a description from the card – often the <a> contains a
        # <p> after the <h3>.
        desc_tag = parent_a.find("p")
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        # The sub-product <ul> usually follows the <a> tag directly.
        sub_list = parent_a.find_next_sibling("ul")
        subproducts: list[dict] = []
        if sub_list:
            for li in sub_list.find_all("li"):
                link = li.find("a")
                if not link:
                    continue
                sub_url = link.get("href", "")
                sub_url = urljoin(BASE_URL, sub_url) if sub_url else ""
                sub_name = link.get_text(strip=True)
                if sub_name:
                    subproducts.append({"name": sub_name, "url": sub_url})

        # Only accept as a valid category if it has sub-products listed.
        # This filters out featured "New Products" cards (FC1500, AEQ Series,
        # ORv3 Shelf) that also use <h3> inside <a> but lack a <ul> sibling.
        if not subproducts:
            continue

        categories.append(
            {
                "name": cat_name,
                "url": cat_url,
                "description": description,
                "subproducts": subproducts,
            }
        )

    return categories


def extract_subproduct_description(soup: BeautifulSoup) -> str:
    """Given a sub-product page soup, try to extract a short clean description.

    Strategy (tuned for the Advanced Energy site):
    1. Look for a <div> with class containing 'description' or 'lead'.
    2. Look for the first substantive <p> that isn't navigation boilerplate.
    3. Fall back to meta description.
    """
    # -- Meta description fallback -------------------------------------------
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content", "").strip():
        return meta["content"].strip()

    # -- Common content containers -------------------------------------------
    for selector in (
        {"class_": re.compile(r"description", re.I)},
        {"class_": re.compile(r"lead", re.I)},
        {"class_": re.compile(r"intro", re.I)},
        {"class_": re.compile(r"product-description", re.I)},
    ):
        container = soup.find("div", **selector)
        if container:
            text = container.get_text(" ", strip=True)
            if len(text) > 40:  # reasonable minimal description length
                return text

    # -- First substantive <p> -----------------------------------------------
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        # Skip short boilerplate
        if len(text) > 60:
            return text

    return "Not found"


# ---------------------------------------------------------------------------
# Filesystem builders
# ---------------------------------------------------------------------------
def write_details(
    path: Path,
    sub_name: str,
    cat_name: str,
    source_url: str,
    description: str,
) -> None:
    """Write the details.txt file for a single sub-product."""
    content = textwrap.dedent(f"""\
        Subproduct Name: {sub_name}
        Category: {cat_name}
        Source Link: {source_url or 'Not found'}
        Description:
        {description}
    """)
    path.write_text(content, encoding="utf-8")


def write_category_summary(path: Path, cat_name: str, sub_names: list[str]) -> None:
    """Write category_summary.txt."""
    total = len(sub_names)
    lines = [f"Category: {cat_name}", f"Total Subproducts: {total}", ""]
    for idx, name in enumerate(sub_names, start=1):
        lines.append(f"{idx}. {name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_tree_text(
    root: Path,
    cat_names: list[str],
    cat_subs: dict[str, list[str]],
) -> str:
    """Produce the all_products_tree.txt content."""
    lines = ["Advanced Energy Products — Full Tree", "=" * 40, ""]
    lines.append(str(root))
    lines.append("│")
    for i, cat in enumerate(cat_names):
        is_last_cat = i == len(cat_names) - 1
        prefix = "└── " if is_last_cat else "├── "
        lines.append(f"{prefix}{cat}/")
        subs = cat_subs.get(cat, [])
        for j, sub in enumerate(subs):
            is_last_sub = j == len(subs) - 1
            indent = "    " if is_last_cat else "│   "
            sub_prefix = "└── " if is_last_sub else "├── "
            lines.append(f"{indent}{sub_prefix}{sub}/")
            lines.append(f"{indent}{'    ' if is_last_sub else '│   '}    details.txt")
        if not is_last_cat:
            lines.append("│")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Core orchestrator
# ---------------------------------------------------------------------------
def run_scraper(output_root: Path, delay: float) -> None:
    """Main scraping & filesystem-construction routine."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # ------------------------------------------------------------------
    # 1. Fetch and parse the main products page
    # ------------------------------------------------------------------
    LOG.info("Fetching products landing page ...")
    main_soup = fetch_page(PRODUCTS_URL, session)
    if not main_soup:
        LOG.critical("Cannot continue without the products page. Exiting.")
        sys.exit(1)

    categories = extract_categories(main_soup)
    if not categories:
        LOG.critical("No categories detected on %s — page structure may have changed.", PRODUCTS_URL)
        sys.exit(1)

    LOG.info("Found %d product categories.\n", len(categories))

    # ------------------------------------------------------------------
    # 2. Create output root
    # ------------------------------------------------------------------
    output_root.mkdir(parents=True, exist_ok=True)

    # Bookkeeping for summaries
    cat_names: list[str] = []
    cat_subs: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # 3. Loop over categories
    # ------------------------------------------------------------------
    for cat_idx, cat in enumerate(categories, start=1):
        cat_name = cat["name"]
        cat_folder = sanitise(cat_name)
        cat_path = output_root / cat_folder
        cat_path.mkdir(parents=True, exist_ok=True)

        sub_names: list[str] = []

        LOG.info("[%d/%d] Category: %s", cat_idx, len(categories), cat_name)

        for sub_idx, sub in enumerate(cat["subproducts"], start=1):
            sub_name = sub["name"]
            sub_url = sub["url"]
            sub_folder = sanitise(sub_name)
            sub_path = cat_path / sub_folder
            sub_path.mkdir(parents=True, exist_ok=True)

            LOG.info("  (%d/%d) %s", sub_idx, len(cat["subproducts"]), sub_name)

            # Try to fetch the sub-product page for a description
            description = "Not found"
            if sub_url:
                LOG.debug("  → %s", sub_url)
                sub_soup = fetch_page(sub_url, session)
                if sub_soup:
                    description = extract_subproduct_description(sub_soup)
                # Be polite
                time.sleep(delay)

            # Write details.txt
            write_details(sub_path / "details.txt", sub_name, cat_name, sub_url, description)
            sub_names.append(sub_name)
            LOG.info("    saved: %s", sub_name)

        # Write category_summary.txt
        write_category_summary(cat_path / "category_summary.txt", cat_name, sub_names)

        cat_names.append(cat_name)
        cat_subs[cat_name] = sub_names

        LOG.info("  → Wrote category_summary.txt for '%s'\n", cat_name)

    # ------------------------------------------------------------------
    # 4. Root-level tree
    # ------------------------------------------------------------------
    tree_text = build_tree_text(output_root, cat_names, cat_subs)
    (output_root / "all_products_tree.txt").write_text(tree_text, encoding="utf-8")
    LOG.info("Wrote all_products_tree.txt — Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Terminal-only scraper for Advanced Energy products."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Root output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay in seconds between sub-product page requests (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    output_root = Path(args.output).resolve()
    LOG.info("Output directory: %s", output_root)
    LOG.info("Inter-request delay: %.1f s", args.delay)
    LOG.info("")

    run_scraper(output_root, args.delay)


if __name__ == "__main__":
    main()
