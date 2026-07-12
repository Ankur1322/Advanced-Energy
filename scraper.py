#!/usr/bin/env python3
"""
Advanced Energy Products Scraper — Recursive Hierarchy Edition
================================================================
Recursively mirrors https://www.advancedenergy.com/en-us/products/ as a
folder hierarchy on disk. Every category/subcategory becomes a folder;
only final product folders contain a single product_details.txt with the
complete category chain plus full product information and a breadcrumb.

Example output:
    output/
        Products/
            Plasma Power Products/
                RF Plasma Power Generators/
                    eVerest RF Generator/
                        product_details.txt
                    Paramount RF Generator/
                        product_details.txt

CLI:
    python scraper.py
    python scraper.py --output output --delay 0.5 --verbose
    python scraper.py --max-depth 6 --max-pages 2000
"""

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = "https://www.advancedenergy.com"
START_URL = f"{BASE_URL}/en-us/products/"
START_LABEL = "Products"

DEFAULT_OUTPUT = "output"
DEFAULT_DELAY = 0.5
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MAX_DEPTH = 8
MAX_PAGES = 3000

USER_AGENT = (
    "Mozilla/5.0 (compatible; AE-HierarchyScraper/2.0; "
    "+https://github.com/example/ae-scraper)"
)

NON_PAGE_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".zip", ".docx", ".xlsx", ".mp4",
)

SECTION_KEYWORDS = {
    "features": ["features", "key features"],
    "specifications": ["specifications", "spec", "technical specifications"],
    "applications": ["applications", "use cases"],
    "benefits": ["benefits", "advantages"],
}

LOG = logging.getLogger("ae_scraper")

_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(message)s" if not verbose else "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def sanitize_name(name: str, fallback: str = "unnamed") -> str:
    """Make a string safe to use as a Windows/Linux folder or file name."""
    if not name or not name.strip():
        return fallback
    safe = re.sub(r"\s+", " ", name).strip()
    safe = _ILLEGAL_CHARS.sub("-", safe)
    safe = safe.strip(". ")
    safe = safe[:150]
    return safe or fallback


def normalize_url(url: str) -> str:
    """Strip query/fragment and normalize trailing slashes so the same
    logical page never gets visited twice under two different URLs."""
    parsed = urlparse(url)
    path = parsed.path
    last_segment = path.rsplit("/", 1)[-1]
    if path and not path.endswith("/") and "." not in last_segment:
        path += "/"
    cleaned = parsed._replace(path=path, query="", fragment="")
    return urlunparse(cleaned)


def absolute_url(base: str, href: str) -> str:
    return normalize_url(urljoin(base, href))


def is_child_path(parent_url: str, candidate_url: str) -> bool:
    """True if candidate_url's path is strictly deeper than and nested
    under parent_url's path."""
    p_path = urlparse(parent_url).path.rstrip("/")
    c_path = urlparse(candidate_url).path.rstrip("/")
    if c_path == p_path:
        return False
    return c_path.startswith(p_path + "/")


def same_domain(base_url: str, url: str) -> bool:
    return urlparse(base_url).netloc == urlparse(url).netloc


def get_main_content(soup: BeautifulSoup):
    """Best-guess main-content node, falling back to <body>. Restricting
    link discovery to this node is what keeps recursion from picking up
    sitewide header/footer navigation links."""
    for selector in ("main", "#main-content", ".main-content", "article", "#content"):
        node = soup.select_one(selector)
        if node:
            return node
    return soup.body or soup


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class ProductInfo:
    name: str
    url: str
    description: str = ""
    features: List[str] = field(default_factory=list)
    specifications: List[str] = field(default_factory=list)
    applications: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    downloads: List[Tuple[str, str]] = field(default_factory=list)
    pdf_links: List[str] = field(default_factory=list)
    images: List[Tuple[str, str]] = field(default_factory=list)
    related_products: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class HierarchyNode:
    name: str
    url: str
    level: int
    description: str = ""
    parent: Optional["HierarchyNode"] = None
    children: List["HierarchyNode"] = field(default_factory=list)
    is_product: bool = False
    skipped: bool = False
    product_info: Optional[ProductInfo] = None


# ---------------------------------------------------------------------------
# State (resume support)
# ---------------------------------------------------------------------------
class StateManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.completed_products: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.completed_products = set(data.get("completed_products", []))
                if self.completed_products:
                    LOG.info("Resuming previous run: %d products already completed.", len(self.completed_products))
            except (json.JSONDecodeError, OSError) as exc:
                LOG.warning("Could not read state file (%s) — starting fresh.", exc)

    def mark_done(self, url: str) -> None:
        self.completed_products.add(url)
        self._save()

    def is_done(self, url: str) -> bool:
        return url in self.completed_products

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"completed_products": sorted(self.completed_products)}
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Crawler — HTTP fetching + in-page child-link discovery
# ---------------------------------------------------------------------------
class Crawler:
    def __init__(self, delay: float, retries: int = MAX_RETRIES):
        self.delay = delay
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                time.sleep(self.delay)
                return BeautifulSoup(resp.text, "html.parser")
            except requests.RequestException as exc:
                LOG.warning("Request %d/%d failed for %s: %s", attempt, self.retries, url, exc)
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        LOG.error("Giving up on %s after %d attempts", url, self.retries)
        return None

    def discover_children(self, soup: BeautifulSoup, page_url: str) -> List[Tuple[str, str]]:
        """Return [(url, link_text), ...] for links in the main content
        area whose path is strictly deeper than page_url's path."""
        content = get_main_content(soup)
        found: Dict[str, str] = {}
        for a in content.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            candidate = absolute_url(BASE_URL, href)
            if not same_domain(BASE_URL, candidate):
                continue
            if candidate.lower().split("?")[0].endswith(NON_PAGE_EXTENSIONS):
                continue
            if not is_child_path(page_url, candidate):
                continue
            name = a.get_text(strip=True)
            if not name:
                continue
            found.setdefault(candidate, name)
        return list(found.items())


# ---------------------------------------------------------------------------
# Parser — page content extraction
# ---------------------------------------------------------------------------
class PageParser:
    def get_description(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content", "").strip():
            return meta["content"].strip()
        content = get_main_content(soup)
        for p in content.find_all("p"):
            text = p.get_text(" ", strip=True)
            if len(text) > 60:
                return text
        return "Not found"

    def _collect_section_items(self, content, keywords: List[str]) -> List[str]:
        items: List[str] = []
        for heading in content.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text(strip=True).lower()
            if not any(kw in heading_text for kw in keywords):
                continue
            for sib in heading.find_next_siblings():
                if sib.name in ("h2", "h3", "h4"):
                    break
                if sib.name in ("ul", "ol"):
                    for li in sib.find_all("li"):
                        text = li.get_text(" ", strip=True)
                        if text:
                            items.append(text)
                elif sib.name == "p":
                    text = sib.get_text(" ", strip=True)
                    if text:
                        items.append(text)
        return items

    def _collect_downloads_and_pdfs(self, content) -> Tuple[List[Tuple[str, str]], List[str]]:
        downloads, pdfs = [], []
        for a in content.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            url = absolute_url(BASE_URL, href)
            if href.lower().split("?")[0].endswith(".pdf"):
                pdfs.append(url)
                downloads.append((text or "Download", url))
            elif any(kw in text.lower() for kw in ("download", "brochure", "datasheet", "whitepaper")):
                downloads.append((text, url))
        return downloads, pdfs

    def _collect_images(self, content) -> List[Tuple[str, str]]:
        images = []
        for img in content.find_all("img", src=True):
            src = img["src"]
            if any(skip in src.lower() for skip in ("logo", "icon", "sprite", "spacer")):
                continue
            alt = img.get("alt", "").strip() or "Image"
            images.append((alt, absolute_url(BASE_URL, src)))
        return images

    def _collect_related_products(self, content) -> List[Tuple[str, str]]:
        related = []
        for heading in content.find_all(["h2", "h3", "h4"]):
            if "related" not in heading.get_text(strip=True).lower():
                continue
            for sib in heading.find_next_siblings():
                if sib.name in ("h2", "h3", "h4"):
                    break
                for a in sib.find_all("a", href=True):
                    text = a.get_text(strip=True)
                    if text:
                        related.append((text, absolute_url(BASE_URL, a["href"])))
        return related

    def parse_product(self, soup: BeautifulSoup, url: str, name: str) -> ProductInfo:
        content = get_main_content(soup)
        info = ProductInfo(name=name, url=url, description=self.get_description(soup))
        info.features = self._collect_section_items(content, SECTION_KEYWORDS["features"])
        info.specifications = self._collect_section_items(content, SECTION_KEYWORDS["specifications"])
        info.applications = self._collect_section_items(content, SECTION_KEYWORDS["applications"])
        info.benefits = self._collect_section_items(content, SECTION_KEYWORDS["benefits"])
        info.downloads, info.pdf_links = self._collect_downloads_and_pdfs(content)
        info.images = self._collect_images(content)
        info.related_products = self._collect_related_products(content)
        return info


# ---------------------------------------------------------------------------
# Hierarchy builder — recursive tree construction
# ---------------------------------------------------------------------------
class HierarchyBuilder:
    """A node is a CATEGORY if the crawler finds child links within its
    main content whose path is strictly deeper. A node with none is a
    PRODUCT leaf, parsed immediately from the page already fetched."""

    def __init__(self, crawler: Crawler, parser: PageParser, state: StateManager,
                 storage: "StorageManager", max_depth: int, max_pages: int):
        self.crawler = crawler
        self.parser = parser
        self.state = state
        self.storage = storage
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.visited: Set[str] = set()
        self.pages_crawled = 0

    def build(self, start_url: str, start_name: str) -> HierarchyNode:
        root = HierarchyNode(name=start_name, url=start_url, level=0)
        self._expand(root)
        return root

    def _expand(self, node: HierarchyNode) -> None:
        if node.url in self.visited:
            return
        self.visited.add(node.url)

        if node.level > self.max_depth:
            LOG.warning("Max depth (%d) reached at %s — stopping here.", self.max_depth, node.url)
            return
        if self.pages_crawled >= self.max_pages:
            LOG.warning("Max page limit (%d) reached — stopping crawl.", self.max_pages)
            return

        if self.state.is_done(node.url) and self.storage.product_already_done(node):
            node.is_product = True
            node.skipped = True
            LOG.info("%sSkip (already saved): %s", "  " * node.level, node.name)
            return

        indent = "  " * node.level
        LOG.info("%sCrawling [L%d]: %s", indent, node.level, node.name)

        try:
            soup = self.crawler.fetch(node.url)
        except Exception as exc:
            LOG.error("%sUnexpected error fetching %s: %s", indent, node.url, exc)
            return

        self.pages_crawled += 1
        if soup is None:
            LOG.error("%sSkipping (fetch failed): %s", indent, node.url)
            return

        try:
            node.description = self.parser.get_description(soup)
            children = self.crawler.discover_children(soup, node.url)

            if not children:
                node.is_product = True
                node.product_info = self.parser.parse_product(soup, node.url, node.name)
                return

            for child_url, child_name in children:
                if child_url in self.visited:
                    continue
                child = HierarchyNode(name=child_name, url=child_url, level=node.level + 1, parent=node)
                node.children.append(child)
                self._expand(child)

        except Exception as exc:
            LOG.error("%sError processing %s: %s", indent, node.url, exc)


# ---------------------------------------------------------------------------
# Formatter — builds product_details.txt content
# ---------------------------------------------------------------------------
class ReportFormatter:
    @staticmethod
    def _ancestor_chain(node: HierarchyNode) -> List[HierarchyNode]:
        chain = []
        cur = node
        while cur is not None:
            chain.append(cur)
            cur = cur.parent
        chain.reverse()
        return chain

    @staticmethod
    def _format_list(title: str, items: Sequence[str]) -> str:
        if not items:
            return f"{title}: Not found\n"
        lines = [f"{title}:"] + [f"  - {item}" for item in items]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_pairs(title: str, pairs: Sequence[Tuple[str, str]]) -> str:
        if not pairs:
            return f"{title}: Not found\n"
        lines = [f"{title}:"] + [f"  - {text}: {url}" for text, url in pairs]
        return "\n".join(lines) + "\n"

    def build(self, product_node: HierarchyNode, info: ProductInfo) -> str:
        chain = self._ancestor_chain(product_node)
        parents = chain[:-1]

        parts: List[str] = []
        parts.append("=" * 78)
        parts.append(f"PRODUCT DETAILS: {info.name}")
        parts.append("=" * 78)
        parts.append("")

        parts.append("-" * 78)
        parts.append("HIERARCHY (root to product, chronological order)")
        parts.append("-" * 78)
        for parent in parents:
            parts.append(f"[Level {parent.level}] Category Name: {parent.name}")
            parts.append(f"Category URL: {parent.url}")
            parts.append(f"Category Description: {parent.description or 'Not found'}")
            parts.append("")

        parts.append("-" * 78)
        parts.append(f"FINAL PRODUCT (Level {product_node.level})")
        parts.append("-" * 78)
        parts.append(f"Product Name: {info.name}")
        parts.append(f"Product URL: {info.url}")
        parts.append("")
        parts.append("Complete Product Description:")
        parts.append(info.description or "Not found")
        parts.append("")

        parts.append(self._format_list("Features", info.features))
        parts.append(self._format_list("Specifications", info.specifications))
        parts.append(self._format_list("Applications", info.applications))
        parts.append(self._format_list("Benefits", info.benefits))
        parts.append(self._format_pairs("Downloads", info.downloads))
        parts.append(self._format_list("PDF Links", info.pdf_links))
        parts.append(self._format_pairs("Images", info.images))
        parts.append(self._format_pairs("Related Products", info.related_products))

        parts.append("-" * 78)
        parts.append("NAVIGATION PATH (Breadcrumb)")
        parts.append("-" * 78)
        parts.append("\n  \u2193\n".join(n.name for n in chain))
        parts.append("")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Storage — folder/file creation
# ---------------------------------------------------------------------------
class StorageManager:
    def __init__(self, output_root: Path, formatter: ReportFormatter, state: StateManager):
        self.output_root = Path(output_root)
        self.formatter = formatter
        self.state = state

    def node_path(self, node: HierarchyNode) -> Path:
        parts = []
        cur = node
        while cur is not None:
            parts.append(sanitize_name(cur.name))
            cur = cur.parent
        parts.reverse()
        return self.output_root.joinpath(*parts)

    def product_already_done(self, node: HierarchyNode) -> bool:
        file_path = self.node_path(node) / "product_details.txt"
        return file_path.exists() and file_path.stat().st_size > 0

    def save_tree(self, root: HierarchyNode) -> None:
        self._save_node(root)

    def _save_node(self, node: HierarchyNode) -> None:
        folder = self.node_path(node)
        folder.mkdir(parents=True, exist_ok=True)

        if node.is_product:
            if node.skipped:
                return
            if node.product_info is None:
                LOG.warning("Leaf with no parsed info, skipping: %s", node.url)
                return
            content = self.formatter.build(node, node.product_info)
            (folder / "product_details.txt").write_text(content, encoding="utf-8")
            self.state.mark_done(node.url)
            LOG.info("Saved: %s", folder / "product_details.txt")
            return

        for child in node.children:
            self._save_node(child)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_scraper(output_root: Path, delay: float, max_depth: int, max_pages: int) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    state_file = output_root / ".scraper_state.json"

    LOG.info("=" * 70)
    LOG.info("Advanced Energy Hierarchical Scraper starting")
    LOG.info("Start URL: %s", START_URL)
    LOG.info("Output dir: %s", output_root.resolve())
    LOG.info("=" * 70)

    crawler = Crawler(delay=delay)
    parser = PageParser()
    state = StateManager(state_file)
    formatter = ReportFormatter()
    storage = StorageManager(output_root, formatter, state)
    builder = HierarchyBuilder(crawler, parser, state, storage, max_depth, max_pages)

    root = builder.build(START_URL, START_LABEL)

    LOG.info("Crawl complete. Writing folder hierarchy to disk ...")
    storage.save_tree(root)

    LOG.info("Done. Pages fetched this run: %d", builder.pages_crawled)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Advanced Energy hierarchical products scraper")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Root output directory (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between requests (seconds)")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH, help="Max recursion depth")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Safety cap on total pages crawled")
    parser.add_argument("--verbose", action="store_true", help="Enable debug-level logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    output_root = Path(args.output).resolve()
    try:
        run_scraper(output_root, args.delay, args.max_depth, args.max_pages)
    except KeyboardInterrupt:
        LOG.warning("Interrupted by user — progress is saved, re-run to resume.")


if __name__ == "__main__":
    main()