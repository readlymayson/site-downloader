"""
Универсальный скрипт для массового скачивания баз документации
и извлечения текста для передачи нейросетям.

Поддерживает:
- Скачивание по списку URL
- Рекурсивное скачивание через sitemap.xml
- Извлечение текста с помощью trafilatura (быстро и качественно)
- Сохранение в удобном формате (TXT, Markdown)
"""

import os
import sys
import time
import json
import requests
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import List, Set, Optional
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠ trafilatura не установлен. Используется базовое извлечение текста.")
    print("   Рекомендуется: pip install trafilatura")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("⚠ beautifulsoup4 не установлен. Некоторые функции могут не работать.")
    print("   Рекомендуется: pip install beautifulsoup4 lxml")


class DocumentationDownloader:
    """Класс для скачивания и извлечения текста из документации"""
    
    def __init__(self, output_dir: str = "downloaded_docs", max_workers: int = 5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.max_workers = max_workers
        self.downloaded_urls: Set[str] = set()
        self.failed_urls: List[tuple] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def extract_text_trafilatura(self, html_content: str, url: str) -> Optional[str]:
        """Извлечение текста с помощью trafilatura (лучшее качество)"""
        if not TRAFILATURA_AVAILABLE:
            return None
        try:
            text = trafilatura.extract(html_content, url=url, output_format='txt')
            return text
        except Exception as e:
            print(f"   ⚠ Ошибка trafilatura: {e}")
            return None
    
    def extract_text_bs4(self, html_content: str) -> str:
        """Извлечение текста с помощью BeautifulSoup (резервный метод)"""
        if not BS4_AVAILABLE:
            # Базовое извлечение без библиотек
            from html.parser import HTMLParser
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                    self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
                    self.in_skip = False
                
                def handle_starttag(self, tag, attrs):
                    if tag in self.skip_tags:
                        self.in_skip = True
                
                def handle_endtag(self, tag):
                    if tag in self.skip_tags:
                        self.in_skip = False
                
                def handle_data(self, data):
                    if not self.in_skip and data.strip():
                        self.text.append(data.strip())
            
            parser = TextExtractor()
            parser.feed(html_content)
            return '\n\n'.join(parser.text)
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            # Удаляем ненужные элементы
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            text = soup.get_text(separator='\n\n', strip=True)
            return text
        except Exception as e:
            print(f"   ⚠ Ошибка BeautifulSoup: {e}")
            return ""
    
    def extract_text(self, html_content: str, url: str) -> str:
        """Извлечение текста (пробует trafilatura, затем BeautifulSoup)"""
        # Пробуем trafilatura (лучшее качество)
        text = self.extract_text_trafilatura(html_content, url)
        if text and len(text.strip()) > 100:
            return text
        
        # Резервный метод
        text = self.extract_text_bs4(html_content)
        return text
    
    def download_page(self, url: str) -> Optional[tuple]:
        """Скачивание одной страницы и извлечение текста"""
        if url in self.downloaded_urls:
            return None
        
        try:
            print(f"📥 Скачиваю: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Извлекаем текст
            text = self.extract_text(response.text, url)
            
            if not text or len(text.strip()) < 50:
                print(f"   ⚠ Мало текста на странице: {url}")
                return None
            
            # Сохраняем
            parsed_url = urlparse(url)
            filename = parsed_url.path.strip('/').replace('/', '_') or 'index'
            if not filename.endswith('.txt'):
                filename += '.txt'
            
            # Очистка имени файла
            filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))[:200]
            
            filepath = self.output_dir / filename
            # Если файл существует, добавляем номер
            counter = 1
            original_filepath = filepath
            while filepath.exists():
                stem = original_filepath.stem
                filepath = self.output_dir / f"{stem}_{counter}.txt"
                counter += 1
            
            filepath.write_text(text, encoding='utf-8')
            self.downloaded_urls.add(url)
            
            print(f"   ✓ Сохранено: {filepath.name} ({len(text)} символов)")
            return (url, filepath, len(text))
            
        except Exception as e:
            print(f"   ✗ Ошибка: {url} - {e}")
            self.failed_urls.append((url, str(e)))
            return None
    
    def get_sitemap_urls(self, base_url: str) -> List[str]:
        """Получение списка URL из sitemap.xml"""
        parsed_base = urlparse(base_url)
        root_base = f"{parsed_base.scheme}://{parsed_base.netloc}"

        sitemap_urls = set()
        for suffix in ['sitemap.xml', 'sitemap_index.xml']:
            sitemap_urls.add(urljoin(root_base, f'/{suffix}'))
            sitemap_urls.add(urljoin(base_url, suffix))

        urls = []
        for sitemap_url in sitemap_urls:
            try:
                print(f"🔍 Проверяю sitemap: {sitemap_url}")
                response = self.session.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    
                    # Обработка sitemap index
                    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
                        loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                        if loc is not None:
                            urls.extend(self.get_sitemap_urls(loc.text))
                    
                    # Обработка обычного sitemap
                    for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                        loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                        if loc is not None:
                            urls.append(loc.text)
                    
                    if urls:
                        print(f"   ✓ Найдено {len(urls)} URL в sitemap")
                        break
            except Exception as e:
                print(f"   ⚠ Не удалось получить sitemap: {e}")
                continue
        
        return urls

    def filter_urls_by_section(self, urls: List[str], section_prefix: str) -> List[str]:
        """Фильтрация URL по префиксу раздела"""
        if not section_prefix:
            return urls

        filtered_urls = []
        for url in urls:
            parsed = urlparse(url)
            if parsed.path.startswith(section_prefix):
                filtered_urls.append(url)

        print(f"   ✓ Отфильтровано {len(filtered_urls)} URL из {len(urls)} по префиксу '{section_prefix}'")
        return filtered_urls

    def download_from_list(self, urls: List[str], use_threading: bool = True):
        """Скачивание по списку URL"""
        print(f"\n🚀 Начинаю скачивание {len(urls)} страниц...")
        
        if use_threading and len(urls) > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.download_page, url): url for url in urls}
                for future in as_completed(futures):
                    future.result()
        else:
            for url in urls:
                self.download_page(url)
                time.sleep(0.5)  # Небольшая задержка между запросами
        
        self.print_summary()
    
    def download_from_sitemap(self, base_url: str, section_prefix: Optional[str] = None):
        """Скачивание всей документации через sitemap.xml"""
        urls = self.get_sitemap_urls(base_url)
        if not urls:
            print("⚠ Sitemap не найден. Попробуйте указать список URL вручную.")
            return

        # Фильтруем URL по разделу, если указан префикс
        if section_prefix:
            urls = self.filter_urls_by_section(urls, section_prefix)

        self.download_from_list(urls)
    
    def save_combined_text(self, output_file: str = "combined_docs.txt"):
        """Сохраняет весь извлеченный текст в один файл"""
        combined_text = []
        combined_text.append(f"# Объединенная документация\n")
        combined_text.append(f"Дата создания: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        combined_text.append(f"Всего страниц: {len(self.downloaded_urls)}\n\n")
        combined_text.append("=" * 80 + "\n\n")
        
        for txt_file in sorted(self.output_dir.glob("*.txt")):
            if txt_file.name == output_file:
                continue
            content = txt_file.read_text(encoding='utf-8')
            combined_text.append(f"## {txt_file.name}\n\n")
            combined_text.append(content)
            combined_text.append("\n\n" + "=" * 80 + "\n\n")
        
        output_path = self.output_dir / output_file
        output_path.write_text(''.join(combined_text), encoding='utf-8')
        print(f"\n📄 Объединенный файл сохранен: {output_path}")
        print(f"   Размер: {len(''.join(combined_text))} символов")
    
    def print_summary(self):
        """Вывод статистики"""
        print("\n" + "=" * 80)
        print("📊 СТАТИСТИКА")
        print("=" * 80)
        print(f"✓ Успешно скачано: {len(self.downloaded_urls)} страниц")
        print(f"✗ Ошибок: {len(self.failed_urls)}")
        print(f"📁 Директория: {self.output_dir.absolute()}")
        
        if self.failed_urls:
            print("\n⚠ Ошибки:")
            for url, error in self.failed_urls[:10]:  # Показываем первые 10
                print(f"   {url}: {error}")
            if len(self.failed_urls) > 10:
                print(f"   ... и еще {len(self.failed_urls) - 10} ошибок")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Массовое скачивание документации и извлечение текста'
    )
    parser.add_argument('--urls', '-u', nargs='+', help='Список URL для скачивания')
    parser.add_argument('--sitemap', '-s', help='Базовый URL для поиска sitemap.xml')
    parser.add_argument('--section-prefix', help='Фильтр по префиксу пути (например: /developers/content/)')
    parser.add_argument('--file', '-f', help='Файл со списком URL (по одному на строку)')
    parser.add_argument('--output', '-o', default='downloaded_docs', help='Директория для сохранения')
    parser.add_argument('--workers', '-w', type=int, default=5, help='Количество потоков')
    parser.add_argument('--combine', '-c', action='store_true', help='Создать объединенный файл')
    
    args = parser.parse_args()
    
    downloader = DocumentationDownloader(
        output_dir=args.output,
        max_workers=args.workers
    )
    
    urls = []
    
    # Получаем URL из разных источников
    if args.urls:
        urls.extend(args.urls)
    
    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            urls.extend([line.strip() for line in file_path.read_text(encoding='utf-8').splitlines() 
                        if line.strip() and not line.startswith('#')])
        else:
            print(f"⚠ Файл не найден: {args.file}")
    
    if args.sitemap:
        downloader.download_from_sitemap(args.sitemap, args.section_prefix)
    elif urls:
        # Если указан section_prefix, фильтруем список URL
        if args.section_prefix:
            urls = downloader.filter_urls_by_section(urls, args.section_prefix)
        downloader.download_from_list(urls)
    else:
        print("❌ Не указаны URL для скачивания!")
        print("\nПримеры использования:")
        print("  python docs_downloader.py --urls https://example.com/doc1 https://example.com/doc2")
        print("  python docs_downloader.py --sitemap https://docs.example.com")
        print("  python docs_downloader.py --sitemap https://docs.example.com --section-prefix /developers/content/")
        print("  python docs_downloader.py --file urls.txt")
        print("  python docs_downloader.py --urls https://example.com --combine")
        return
    
    if args.combine:
        downloader.save_combined_text()


if __name__ == "__main__":
    main()
