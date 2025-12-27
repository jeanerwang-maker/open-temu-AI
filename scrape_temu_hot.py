#!/usr/bin/env python3
"""Scrape Temu front-page hot product data.

This script fetches a Temu front page URL, extracts embedded JSON data,
then searches for product-like objects that resemble "hot" or featured items.

Usage:
  python scrape_temu_hot.py --url https://www.temu.com --limit 50 --format json --output hot.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup


@dataclass
class Product:
    goods_id: str
    title: str
    price: str | None
    image: str | None
    tags: list[str]
    source_path: str


def fetch_html(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_embedded_json(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    json_blobs: list[dict[str, Any]] = []

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            json_blobs.append(json.loads(next_data.string))
        except json.JSONDecodeError:
            pass

    for script in soup.find_all("script"):
        if not script.string:
            continue
        text = script.string.strip()
        if text.startswith("window.__INITIAL_STATE__"):
            match = re.search(r"window.__INITIAL_STATE__\s*=\s*(\{.*\});?", text)
            if match:
                try:
                    json_blobs.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    continue
    return json_blobs


def iter_dicts(obj: Any, path: str = "root") -> Iterable[tuple[str, dict[str, Any]]]:
    queue = deque([(path, obj)])
    while queue:
        current_path, current = queue.popleft()
        if isinstance(current, dict):
            yield current_path, current
            for key, value in current.items():
                queue.append((f"{current_path}.{key}", value))
        elif isinstance(current, list):
            for idx, value in enumerate(current):
                queue.append((f"{current_path}[{idx}]", value))


def normalize_price(data: dict[str, Any]) -> str | None:
    for key in ("price", "priceStr", "price_str", "price_text"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    if isinstance(data.get("price"), (int, float)):
        return str(data["price"])
    return None


def collect_products(data: dict[str, Any]) -> list[Product]:
    products: list[Product] = []
    seen_ids: set[str] = set()
    for path, item in iter_dicts(data):
        if not isinstance(item, dict):
            continue
        goods_id = item.get("goodsId") or item.get("goods_id") or item.get("id")
        title = item.get("title") or item.get("goodsName") or item.get("goods_name")
        if not goods_id or not title:
            continue
        goods_id_str = str(goods_id)
        if goods_id_str in seen_ids:
            continue
        tags_raw = item.get("tags") or item.get("label") or item.get("labels")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [str(tag) for tag in tags_raw if tag]
        elif isinstance(tags_raw, str):
            tags = [tags_raw]
        products.append(
            Product(
                goods_id=goods_id_str,
                title=str(title),
                price=normalize_price(item),
                image=item.get("image") or item.get("thumb") or item.get("img"),
                tags=tags,
                source_path=path,
            )
        )
        seen_ids.add(goods_id_str)
    return products


def filter_hot_products(products: list[Product]) -> list[Product]:
    hot_keywords = {"hot", "热销", "爆款", "热卖", "bestseller", "best seller"}
    hot_items: list[Product] = []
    for product in products:
        if any(keyword in tag.lower() for tag in product.tags for keyword in hot_keywords):
            hot_items.append(product)
            continue
        lower_title = product.title.lower()
        if any(keyword in lower_title for keyword in hot_keywords):
            hot_items.append(product)
    return hot_items


def save_output(products: list[Product], output: Path, fmt: str) -> None:
    if fmt == "json":
        payload = [asdict(product) for product in products]
        with output.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return

    if fmt == "csv":
        import csv

        with output.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["goods_id", "title", "price", "image", "tags", "source_path"],
            )
            writer.writeheader()
            for product in products:
                row = asdict(product)
                row["tags"] = ",".join(product.tags)
                writer.writerow(row)
        return

    raise ValueError(f"Unsupported format: {fmt}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Temu front-page hot products.")
    parser.add_argument("--url", default="https://www.temu.com", help="Temu front-page URL")
    parser.add_argument("--limit", type=int, default=50, help="Max number of products to output")
    parser.add_argument("--format", choices=["json", "csv"], default="csv")
    parser.add_argument("--output", default="temu_hot_products.csv")
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "Desktop"),
        help="Directory to store output files (default: ~/Desktop)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Seconds between runs for scheduled scraping (0 = run once)",
    )
    parser.add_argument(
        "--html-file",
        help="Parse a local HTML file instead of fetching from the network",
    )
    parser.add_argument(
        "--save-html",
        action="store_true",
        help="Save the fetched HTML to the output directory for debugging",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include all products (skip hot-only filtering)",
    )
    return parser.parse_args()


def build_output_path(output_dir: Path, output_name: str, fmt: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_name)
    stem = base.stem or "temu_hot_products"
    suffix = base.suffix or f".{fmt}"
    return output_dir / f"{stem}_{timestamp}{suffix}"


def run_once(args: argparse.Namespace) -> int:
    if args.html_file:
        html_path = Path(args.html_file)
        if not html_path.exists():
            print(f"HTML file not found: {html_path}", file=sys.stderr)
            return 1
        html = html_path.read_text(encoding="utf-8")
    else:
        try:
            html = fetch_html(args.url)
        except requests.RequestException as exc:
            print(f"Failed to fetch {args.url}: {exc}", file=sys.stderr)
            return 1

    output_dir = Path(args.output_dir)
    if args.save_html and not args.html_file:
        html_path = build_output_path(output_dir, "temu_page.html", "html")
        html_path.write_text(html, encoding="utf-8")
        print(f"Saved HTML snapshot to {html_path}")

    json_blobs = extract_embedded_json(html)
    if not json_blobs:
        print("No embedded JSON data found. Temu may have changed the page structure.", file=sys.stderr)
        return 2

    products: list[Product] = []
    for blob in json_blobs:
        products.extend(collect_products(blob))

    if not products:
        print("No product-like data found in embedded JSON.", file=sys.stderr)
        return 3

    if not args.include_all:
        products = filter_hot_products(products)

    products = products[: args.limit]
    output_path = build_output_path(output_dir, args.output, args.format)
    save_output(products, output_path, args.format)

    print(f"Saved {len(products)} items to {output_path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        return run_once(args)

    print(f"Scheduled scraping every {args.interval} seconds. Press Ctrl+C to stop.")
    while True:
        exit_code = run_once(args)
        if exit_code != 0:
            return exit_code
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
