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
IMAGE_ATTRS = (
    "src",
    "data-src",
    "data-lazy-src",
    "data-original",
    "data-image",
    "data-bg",
    "poster",
)
GENERIC_IMAGE_HINTS = (
    "ae_logo",
    "logo",
    "wechat",
    "qr",
    "support-image",
    "ae-placholder",
    "placeholder",
    "/technical-content/",
    "brochure",
    "whitepaper",
    "application-note",
    "pdf.png",
)
PRODUCT_IMAGE_HINTS = (
    "product",
    "series",
    "thumbnail",
    "fr-wp",
    "fl-wp",
    "bb-wp",
    "t300x300",
    "t700x700",
    "getattachment",
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


def extract_subproduct_image(soup: BeautifulSoup) -> str:
    """Given a sub-product page soup, try to extract the main product image URL.

    Strategy:
    1. Collect Open Graph/Twitter image meta tags.
    2. Collect lazy-loaded images from src/data-src/srcset style attributes.
    3. Prefer product/gallery/series-card images over logos, placeholders, and
       generic support/technical-content artwork.
    4. Resolve as absolute URL.
    """
    images = extract_subproduct_images(soup, limit=1)
    if images:
        return images[0]

    return "Not found"


def _first_srcset_url(srcset: str) -> str:
    """Return the first URL from an HTML srcset attribute."""
    if not srcset:
        return ""
    first_candidate = srcset.split(",", 1)[0].strip()
    return first_candidate.split(" ", 1)[0].strip()


def _image_score(url: str, context: str) -> int:
    """Score image candidates so real product photos beat generic assets."""
    haystack = f"{url} {context}".lower()

    if not url:
        return -100
    if url.lower().startswith("data:"):
        return -100
    if url.lower().split("?", 1)[0].endswith(".svg"):
        return -50

    score = 0
    for hint in PRODUCT_IMAGE_HINTS:
        if hint in haystack:
            score += 10
    for hint in GENERIC_IMAGE_HINTS:
        if hint in haystack:
            score -= 25
    if any(ext in url.lower().split("?", 1)[0] for ext in (".jpg", ".jpeg", ".png", ".webp")):
        score += 5
    return score


def _add_image_candidate(
    candidates: list[tuple[int, int, str]],
    seen: set[str],
    raw_url: str,
    context: str,
    position: int,
) -> None:
    """Normalize and append one image candidate if it is worth considering."""
    if not raw_url:
        return
    absolute_url = urljoin(BASE_URL, raw_url.strip())
    if absolute_url in seen:
        return
    seen.add(absolute_url)
    candidates.append((_image_score(absolute_url, context), position, absolute_url))


def extract_subproduct_images(soup: BeautifulSoup, limit: int = 5) -> list[str]:
    """Extract ranked product image URLs from a sub-product page."""
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    position = 0

    for attrs in (
        {"property": "og:image"},
        {"property": "og:image:secure_url"},
        {"name": "twitter:image"},
        {"name": "twitter:image:src"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content", "").strip():
            _add_image_candidate(candidates, seen, meta["content"], " ".join(attrs.values()), position)
            position += 1

    preferred_containers = soup.find_all(
        ["section", "div", "figure"],
        class_=re.compile(r"(product|hero|gallery|carousel|series|image)", re.I),
    )
    for container in preferred_containers:
        context = " ".join(container.get("class", []))
        for img in container.find_all("img"):
            img_context = f"{context} {' '.join(img.get('class', []))} {img.get('alt', '')}"
            for attr in IMAGE_ATTRS:
                _add_image_candidate(candidates, seen, img.get(attr, ""), img_context, position)
            _add_image_candidate(candidates, seen, _first_srcset_url(img.get("srcset", "")), img_context, position)
            _add_image_candidate(candidates, seen, _first_srcset_url(img.get("data-srcset", "")), img_context, position)
            position += 1

    for img in soup.find_all("img"):
        context = f"{' '.join(img.get('class', []))} {img.get('alt', '')}"
        for attr in IMAGE_ATTRS:
            _add_image_candidate(candidates, seen, img.get(attr, ""), context, position)
        _add_image_candidate(candidates, seen, _first_srcset_url(img.get("srcset", "")), context, position)
        _add_image_candidate(candidates, seen, _first_srcset_url(img.get("data-srcset", "")), context, position)
        position += 1

    usable = [item for item in candidates if item[0] >= 0]
    fallback = candidates if candidates else []
    ranked = sorted(usable or fallback, key=lambda item: (-item[0], item[1]))
    return [url for _, _, url in ranked[:limit]]


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
    sub_path: Path,
    sub_name: str,
    cat_name: str,
    source_url: str,
    description: str,
    image_url: str | list[str] = "Not found",
) -> None:
    """Write both details.txt and product_details.txt with a rich layout."""
    image_urls = image_url if isinstance(image_url, list) else [image_url]
    image_urls = [url for url in image_urls if url and url != "Not found"]
    image_lines = "\n".join(f"          - Image: {url}" for url in image_urls) or "          - Image: Not found"

    content = textwrap.dedent(f"""\
        ==============================================================================
        PRODUCT DETAILS: {sub_name}
        ==============================================================================

        ------------------------------------------------------------------------------
        HIERARCHY (root to product, chronological order)
        ------------------------------------------------------------------------------
        [Level 0] Category Name: Products
        Category URL: {PRODUCTS_URL}
        Category Description: Find reliable power supplies and sensing products.

        [Level 1] Category Name: {cat_name}
        Category URL: {source_url or 'Not found'}

        ------------------------------------------------------------------------------
        FINAL PRODUCT (Level 2)
        ------------------------------------------------------------------------------
        Product Name: {sub_name}
        Product URL: {source_url or 'Not found'}

        Complete Product Description:
        {description}

        Features: Not found

        Specifications: Not found

        Applications: Not found

        Benefits: Not found

        Downloads: Not found

        PDF Links: Not found

        Images:
{image_lines}

        Related Products: Not found

        ------------------------------------------------------------------------------
        NAVIGATION PATH (Breadcrumb)
        ------------------------------------------------------------------------------
        Products
          ↓
        {cat_name}
          ↓
        {sub_name}
    """)
    sub_path.joinpath("product_details.txt").write_text(content, encoding="utf-8")
    sub_path.joinpath("details.txt").write_text(content, encoding="utf-8")


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

            # Try to fetch the sub-product page for description and image
            description = "Not found"
            image_urls: list[str] = []
            if sub_url:
                LOG.debug("  → %s", sub_url)
                sub_soup = fetch_page(sub_url, session)
                if sub_soup:
                    description = extract_subproduct_description(sub_soup)
                    image_urls = extract_subproduct_images(sub_soup)
                # Be polite
                time.sleep(delay)

            # Write details files
            write_details(sub_path, sub_name, cat_name, sub_url, description, image_urls or "Not found")
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
