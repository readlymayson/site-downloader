"""
Универсальный парсер ссылок из навигационных деревьев.

Пример использования:

python scripts/collect_links.py \
  --source tree_amocrm_docs \
  --selector ".nav_aside__list a" \
  --prefix /developers/content/ \
  --output amocrm_links.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def fetch_content(source: str) -> str:
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")

    response = requests.get(source, timeout=20)
    response.raise_for_status()
    return response.text


def normalize_href(href: str, base_url: Optional[str]) -> Optional[str]:
    href = href.strip()
    if not href or href.startswith(("mailto:", "tel:")):
        return None

    if href.startswith("//"):
        return f"https:{href}"

    if base_url:
        href = urljoin(base_url, href)
    elif href.startswith("/"):
        # Try to keep minimal context if no base was provided
        parsed = urlparse(href)
        if parsed.netloc:
            return href
        return None

    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"}:
        return None

    return href


def collect_links(
    html: str,
    selector: str,
    base_url: Optional[str],
    prefixes: Optional[List[str]],
    domains: Optional[List[str]],
) -> Set[str]:
    soup = BeautifulSoup(html, "lxml")
    links: Set[str] = set()

    for anchor in soup.select(selector):
        href = anchor.get("href")
        if not href:
            continue
        normalized = normalize_href(href, base_url)
        if not normalized:
            continue

        parsed = urlparse(normalized)
        if domains and parsed.netloc not in domains:
            continue

        if prefixes:
            if not any(parsed.path.startswith(prefix) for prefix in prefixes):
                continue

        links.add(normalized)

    return links


def main():
    parser = argparse.ArgumentParser(description="Собирает ссылки из HTML-дерева документации")
    parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="URL или путь к HTML (например: ранее сохранённая боковая навигация)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="collected_links.txt",
        help="Путь для сохранения списка ссылок",
    )
    parser.add_argument(
        "--selector",
        default="a",
        help="CSS-селектор для поиска ссылок (по умолчанию любые <a>)",
    )
    parser.add_argument(
        "--base-url",
        help="Базовый URL для нормализации относительных путей",
    )
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Фильтр по префиксу пути (можно передать несколько раз)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Ограничить домены (можно передать несколько раз)",
    )

    args = parser.parse_args()

    content = fetch_content(args.source)
    links = collect_links(
        content,
        selector=args.selector,
        base_url=args.base_url,
        prefixes=args.prefix or None,
        domains=args.domain or None,
    )

    if not links:
        raise SystemExit("⚠ Не удалось найти подходящие ссылки")

    output_path = Path(args.output)
    output_path.write_text("\n".join(sorted(links)), encoding="utf-8")
    print(f"Собрано {len(links)} ссылок и сохранено в {output_path}")


if __name__ == "__main__":
    main()
