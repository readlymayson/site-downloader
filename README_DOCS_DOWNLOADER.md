# Массовое скачивание документации

Универсальный инструмент для быстрого скачивания баз документации и извлечения текста для передачи нейросетям.

## Возможности

- ✅ **Массовое скачивание** - обрабатывает сотни страниц автоматически
- ✅ **Извлечение текста** - использует trafilatura для качественного извлечения
- ✅ **Поддержка sitemap.xml** - автоматически находит все страницы документации
- ✅ **Многопоточность** - быстрое скачивание нескольких страниц одновременно
- ✅ **Объединение файлов** - создает один большой файл со всей документацией
- ✅ **Умная обработка** - удаляет рекламу, навигацию, скрипты

## Установка

```bash
pip install -r requirements_docs_downloader.txt
```

Или минимальная установка:
```bash
pip install trafilatura requests beautifulsoup4 lxml
```

## Использование

### 1. Скачивание по списку URL

```bash
python docs_downloader.py --urls https://docs.example.com/page1 https://docs.example.com/page2
```

### 2. Скачивание через sitemap.xml

```bash
python docs_downloader.py --sitemap https://docs.example.com
```

Скрипт автоматически найдет `sitemap.xml` и скачает все страницы из него.

### 2.1. Скачивание определенного раздела

```bash
python docs_downloader.py --sitemap https://www.amocrm.ru/developers/content/ --section-prefix /developers/content/
```

Если раздел (например, документация Wazzup или любой другой портал) поставляется с навигационным деревом, можно использовать скрипт `scripts/collect_links.py`, чтобы извлечь ссылки и передать их в `--file`.

### 3. Скачивание из файла со списком URL

Создайте файл `urls.txt`:
```
https://docs.example.com/page1
https://docs.example.com/page2
https://docs.example.com/page3
```

или сгенерируйте ссылки из документационного дерева:

```bash
python scripts/collect_links.py \
  --source tree_amocrm_docs \
  --selector ".nav_aside__list a" \
  --base-url https://www.amocrm.ru \
  --prefix /developers/content/ \
  --output amocrm_links.txt

python docs_downloader.py --file amocrm_links.txt --output amocrm_docs
```

Для Wazzup (или любого другого сайта с похожим деревом) достаточно указать соответствующий `--selector`, `--base-url` и префиксы.

### 4. Скачивание с объединением в один файл

```bash
python docs_downloader.py --sitemap https://docs.example.com --combine
```

Это создаст файл `combined_docs.txt` со всей документацией в одном файле.

### 5. Настройка количества потоков

```bash
python docs_downloader.py --sitemap https://docs.example.com --workers 10
```

## Параметры

- `--urls`, `-u` - Список URL для скачивания
- `--sitemap`, `-s` - Базовый URL для поиска sitemap.xml
- `--section-prefix` - Фильтр по префиксу пути (например: `/developers/content/`)
- `--file`, `-f` - Файл со списком URL (по одному на строку)
- `--output`, `-o` - Директория для сохранения (по умолчанию: `downloaded_docs`)
- `--workers`, `-w` - Количество потоков (по умолчанию: 5)
- `--combine`, `-c` - Создать объединенный файл со всей документацией

## Примеры использования

### Скачать документацию Python

```bash
python docs_downloader.py --sitemap https://docs.python.org/3 --combine
```

### Скачать несколько конкретных страниц

```bash
python docs_downloader.py --urls \
  https://docs.python.org/3/tutorial/index.html \
  https://docs.python.org/3/library/index.html \
  --output python_docs
```

### Массовое скачивание с файла

```bash
# Создайте urls.txt со списком URL
python docs_downloader.py --file urls.txt --workers 10 --combine
```

## Альтернативные инструменты

### 1. wget (для Windows: через Git Bash или WSL)

```bash
# Скачать весь сайт
wget --recursive --level=2 --convert-links --adjust-extension \
     --page-requisites --no-parent https://docs.example.com

# Скачать только HTML
wget --recursive --no-parent --html-extension \
     --convert-links --domains=docs.example.com https://docs.example.com
```

### 2. HTTrack (графический интерфейс)

- Скачать: https://www.httrack.com/
- Простой интерфейс для скачивания целых сайтов
- Подходит для неопытных пользователей

### 3. Scrapy (для сложных случаев)

```bash
pip install scrapy
# Требует создания проекта и настройки
```

## Формат вывода

Все файлы сохраняются в директории `downloaded_docs/` (или указанной в `--output`):
- Каждая страница сохраняется в отдельный `.txt` файл
- Текст очищен от HTML, рекламы, навигации
- Сохранено форматирование (абзацы, списки)
- При использовании `--combine` создается один большой файл

## Рекомендации

1. **Для быстрого разового скачивания** - используйте онлайн-инструменты:
   - https://pr-cy.ru/page-to-text/ (для одной страницы)
   
2. **Для массового скачивания** - используйте этот скрипт с `--sitemap`

3. **Для очень больших сайтов** - используйте `wget` или `httrack`

4. **Для JavaScript-сайтов** - может потребоваться Selenium (не включен в базовую версию)

## Обработка ошибок

Скрипт автоматически:
- Пропускает уже скачанные страницы
- Сохраняет список ошибок
- Продолжает работу при ошибках на отдельных страницах
- Выводит статистику в конце

## Производительность

- **trafilatura** - самый быстрый и качественный метод извлечения текста
- **Многопоточность** - ускоряет скачивание в 5-10 раз
- **Кэширование** - не скачивает повторно уже обработанные URL

## Лицензия

Свободное использование. Убедитесь, что соблюдаете правила использования сайтов и авторские права.
