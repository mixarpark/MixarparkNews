import os
import re
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# ==========================================
# 1. НАСТРОЙКИ И КОНСТАНТЫ
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
SERPER_API_KEY = os.getenv('SERPER_API_KEY') # Ключ для поиска

PENDING_FILE = "pending_sources.txt"
EXISTING_SOURCES_FILE = "source_links.txt"

# Формируем запросы для поиска блогов и новостей
SEARCH_QUERIES = [
    '"audio augmented reality" blog OR news',
    '"phygital" technology news',
    '"spatial audio" AND "augmented reality" articles',
    '"smart glasses" AR XR blog'
]

# Ключевые слова для валидации лент
KEYWORDS = ['ar', 'phygital', 'audio', 'immersive', 'xr', 'augmented reality', 'spatial audio']

# Исключаем мусорные домены (соцсети, магазины)
BLACKLIST_DOMAINS = {
    'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'wikipedia.org', 'amazon.com', 'reddit.com', 'pinterest.com', 'tiktok.com'
}

REQ_TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsScoutBot/1.0"
}

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_existing_domains():
    """Получает список уже известных доменов, чтобы не проверять их заново"""
    if not os.path.exists(EXISTING_SOURCES_FILE):
        return set()
    with open(EXISTING_SOURCES_FILE, "r", encoding="utf-8") as f:
        urls = f.read().splitlines()
    
    domains = set()
    for url in urls:
        try:
            domain = urlparse(url).netloc.replace("www.", "")
            if domain: domains.add(domain)
        except: pass
    return domains

def find_rss_on_page(url):
    """Ищет ссылку на RSS в HTML коде страницы"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        rss_links = soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml', re.IGNORECASE))
        for link in rss_links:
            href = link.get('href')
            if href:
                return urljoin(url, href)
    except Exception as e:
        print(f"⚠️ RSS не найден на {url} ({e})")
    return None

def validate_rss(rss_url):
    """Проверяет, живая ли лента и есть ли в ней наши ключи"""
    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=REQ_TIMEOUT)
        feed = feedparser.parse(response.content)
        
        if not feed.entries:
            return False, "Лента пуста"
            
        for entry in feed.entries[:10]:
            title_summary = (getattr(entry, 'title', '') + " " + getattr(entry, 'summary', '')).lower()
            if any(kw.lower() in title_summary for kw in KEYWORDS):
                site_title = getattr(feed.feed, 'title', 'Неизвестный источник')
                return True, site_title
                
        return False, "Нет релевантных статей"
    except Exception as e:
        return False, f"Ошибка парсинга: {e}"

def send_telegram_alert(new_sources):
    """Отправляет отчет Разведчика в Telegram"""
    if not new_sources:
        return
    text = "🕵️‍♂️ **Отчет Разведчика (Google Search API)**\n\nНайдено новых источников с RSS:\n\n"
    for i, (title, url) in enumerate(new_sources.items(), 1):
        text += f"{i}. {title}\n🔗 {url}\n\n"
    text += "Добавьте подходящие в `source_links.txt`."
    
    tg_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(tg_api, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)

# ==========================================
# 3. ОСНОВНАЯ ЛОГИКА (ПОИСК ЧЕРЕЗ SERPER.DEV)
# ==========================================
print("🚀 Разведчик начинает поиск через Serper (Google Search)...")

if not SERPER_API_KEY:
    print("❌ Ошибка: Не задан ключ SERPER_API_KEY в секретах GitHub!")
    exit(1)

existing_domains = get_existing_domains()
found_external_urls = set()

# Шаг 1: Опрос Serper API
for query in SEARCH_QUERIES:
    print(f"📡 Ищем в Google (через Serper): {query}")
    try:
        url = "https://google.serper.dev/search"
        
        # Убрали json.dumps() и параметр num, чтобы исключить конфликт форматов
        payload = {
            "q": query
        }
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Передаем данные через параметр json= (requests сам всё правильно упакует)
        resp = requests.post(url, headers=headers, json=payload, timeout=REQ_TIMEOUT)
        
        # Если статус не 200 (ОК), печатаем конкретную ошибку, которую вернул сервер!
        if resp.status_code != 200:
            print(f"⚠️ Ошибка от Serper (Код {resp.status_code}): {resp.text}")
            continue
            
        data = resp.json()
        
        # У Serper органическая выдача лежит в ключе 'organic'
        items = data.get('organic', [])
        for item in items:
            link = item.get('link', '')
            if link:
                domain = urlparse(link).netloc.replace("www.", "")
                
                # Фильтруем дубли, блэклист и уже известные нам домены
                if domain and domain not in existing_domains and not any(bl in domain for bl in BLACKLIST_DOMAINS):
                    base_url = f"{urlparse(link).scheme}://{urlparse(link).netloc}"
                    found_external_urls.add(base_url)
                    
    except Exception as e:
        print(f"❌ Ошибка при запросе к Serper API: {e}")
        
print(f"🔍 Найдено уникальных потенциальных доменов: {len(found_external_urls)}")

# Шаг 2: Поиск и валидация RSS на найденных сайтах
valid_new_sources = {}

for base_url in found_external_urls:
    print(f"🔎 Ищем RSS на {base_url}...")
    rss_url = find_rss_on_page(base_url)
    
    if rss_url:
        print(f"   [+] Найден возможный RSS: {rss_url}")
        is_valid, info = validate_rss(rss_url)
        
        if is_valid:
            print(f"   ✅ ВАЛИДНО! {info}")
            valid_new_sources[info] = rss_url
        else:
            print(f"   [-] Отклонено: {info}")

# Шаг 3: Сохранение и Уведомление
if valid_new_sources:
    # 1. Записываем ссылки сразу в ОСНОВНУЮ базу для бота
    with open(EXISTING_SOURCES_FILE, "a", encoding="utf-8") as f:
        for title, url in valid_new_sources.items():
            f.write(f"{url}\n")
            
    # 2. Очищаем файл карантина, так как мы всё добавили в базу
    # (Создаем/перезаписываем пустой файл, чтобы git не ругался на его отсутствие)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        f.write("")
        
    # 3. Отправляем сообщение в ТГ, чтобы ты знал о пополнении базы
    
    def send_telegram_alert(new_sources):
    """Отправляет отчет Разведчика в Telegram"""
    if not new_sources:
        return
        
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Ошибка ТГ: Не найдены BOT_TOKEN или CHAT_ID. Сообщение не отправлено.")
        return

    text = "🕵️‍♂️ **Отчет Разведчика (Google Search API)**\n\nНайдено новых источников с RSS:\n\n"
    for i, (title, url) in enumerate(new_sources.items(), 1):
        text += f"{i}. {title}\n🔗 {url}\n\n"
    text += "Они были автоматически добавлены в `source_links.txt`."
    
    tg_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        # Убрали parse_mode="Markdown", так как некоторые URL могут ломать разметку и вызывать ошибку 400
        resp = requests.post(tg_api, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        
        if resp.status_code != 200:
            print(f"⚠️ Ошибка отправки в Телеграм: {resp.status_code} - {resp.text}")
        else:
            print("✅ Отчет успешно отправлен в Telegram!")
            
    except Exception as e:
        print(f"❌ Критическая ошибка при отправке в Телеграм: {e}")
    
    print(f"🎉 Разведка завершена! {len(valid_new_sources)} новых источников добавлено в базу.")
else:
    print("🤷‍♂️ Новых валидных источников сегодня не найдено.")
