"""
Debug helper — run this after a failed scrape to inspect what HTML
the scraper actually received from each site.

Usage (inside Docker):
    docker compose exec worker python debug_html.py

It reads the /tmp/debug_*.html snapshots saved by the scraper and
prints what listing-related CSS classes were found, plus a text snippet.
"""
import glob
import os
from bs4 import BeautifulSoup

snapshots = sorted(glob.glob("/tmp/debug_*.html"))
if not snapshots:
    print("No snapshots found. Run a search first, then re-run this script.")
    raise SystemExit

for path in snapshots:
    source = os.path.basename(path)
    print(f"\n{'='*60}")
    print(f"FILE: {source}")
    print(f"{'='*60}")

    with open(path, encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string if soup.title else "no title"
    print(f"Title:   {title}")
    print(f"Length:  {len(html):,} chars")

    # Detect block-level elements (likely listing cards)
    all_classes = set()
    for tag in soup.find_all(class_=True):
        for c in tag.get("class", []):
            all_classes.add(c)

    keywords = ["list", "item", "card", "cassette", "property", "bukken",
                "building", "result", "rent", "merge", "unit", "chintai",
                "price", "bukken", "room", "flat", "apartment"]
    hits = [c for c in all_classes if any(k in c.lower() for k in keywords)]

    print(f"\nListing-related classes ({len(hits)}):")
    for c in sorted(hits)[:40]:
        count = len(soup.select(f".{c}"))
        print(f"  .{c}  ({count} elements)")

    print(f"\nBody text (first 400 chars):")
    print(soup.get_text()[:400].strip())
