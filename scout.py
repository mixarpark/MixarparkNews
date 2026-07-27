import os
import re
import json # Добавили json
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# ==========================================
# 1. НАСТРОЙКИ И КОНСТАНТЫ
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
SERPER_API_KEY = os.getenv('SERPER_API_KEY') # Новый ключ

# ... (Оставляем списки KEYWORDS, BLACKLIST_DOMAINS и функции без изменений) ...

# ==========================================
# 3. ОСНОВНАЯ ЛОГИКА (ПОИСК ЧЕРЕЗ SERPER.DEV)
# ==========================================
print("🚀 Разведчик начинает поиск через Serper (Google Search)...")

if not SERPER_API_KEY:
    print("❌ Ошибка: Не задан ключ SERPER_API_KEY!")
    exit(1)

existing_domains = get_existing_domains()
found_external_urls = set()

# Шаг 1: Опрос Serper API (Ищем в Google)
for query in SEARCH_QUERIES:
    print(f"📡 Ищем: {query}")
    try:
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "num": 15 # Берем топ-15 результатов
        })
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        
        resp = requests.post(url, headers=headers, data=payload, timeout=REQ_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        # У Serper органическая выдача лежит в ключе 'organic'
        items = data.get('organic', [])
        for item in items:
            link = item.get('link', '')
            if link:
                domain = urlparse(link).netloc.replace("www.", "")
                
                if domain and domain not in existing_domains and not any(bl in domain for bl in BLACKLIST_DOMAINS):
                    base_url = f"{urlparse(link).scheme}://{urlparse(link).netloc}"
                    found_external_urls.add(base_url)
                    
    except Exception as e:
        print(f"❌ Ошибка при запросе к Serper API: {e}")

print(f"🔍 Найдено уникальных потенциальных доменов: {len(found_external_urls)}")

# ... (Шаг 2 и Шаг 3 с проверкой RSS остаются без изменений) ...
