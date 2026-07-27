import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# ==========================================
# 1. НАСТРОЙКИ И КОНСТАНТЫ
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN') # Используем те же секреты
CHAT_ID = os.getenv('CHAT_ID')

PENDING_FILE = "pending_sources.txt"
EXISTING_SOURCES_FILE = "source_links.txt"

# Сабреддиты для мониторинга
SUBREDDITS = ['augmentedreality', 'spatialcomputing', 'AR_MR_XR']
# Ключевые слова для фильтрации (чтобы не брать всё подряд)
KEYWORDS = ['ar', 'phygital', 'audio', 'immersive', 'xr', 'augmented reality', 'spatial audio']

# Жесткие таймауты
REQ_TIMEOUT = 10

# Маскируемся (Reddit требует уникальный User-Agent, иначе блокирует запросы)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsScoutBot/1.0 (by AR_PH_Researcher)"
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
    
    # Извлекаем только домены (например, из https://feed.com/rss -> feed.com)
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
        
        # Ищем стандартный тег: <link rel="alternate" type="application/rss+xml" ...>
        rss_links = soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml', re.IGNORECASE))
        
        for link in rss_links:
            href = link.get('href')
            if href:
                # Если ссылка относительная (например, /feed), делаем её абсолютной
                return urljoin(url, href)
    except Exception as e:
        print(f"⚠️ Ошибка поиска RSS на {url}: {e}")
    return None

def validate_rss(rss_url):
    """Проверяет, живая ли лента и есть ли в ней наши ключевые слова"""
    try:
        response = requests.get(rss_url, headers=HEADERS, timeout=REQ_TIMEOUT)
        feed = feedparser.parse(response.content)
        
        if not feed.entries:
            return False, "Лента пуста или не читается"
            
        # Проверяем последние 10 статей на наличие нужных слов
        for entry in feed.entries[:10]:
            title_summary = (getattr(entry, 'title', '') + " " + getattr(entry, 'summary', '')).lower()
            if any(kw.lower() in title_summary for kw in KEYWORDS):
                # Нашли хотя бы одно совпадение — берем!
                site_title = getattr(feed.feed, 'title', 'Неизвестный источник')
                return True, site_title
                
        return False, "Нет релевантных статей за последнее время"
    except Exception as e:
        return False, f"Ошибка парсинга: {e}"

def send_telegram_alert(new_sources):
    """Отправляет отчет Разведчика в Telegram"""
    if not new_sources:
        return
        
    text = "🕵️‍♂️ **Отчет Разведчика**\n\nНайдено новых источников с RSS:\n\n"
    for i, (title, url) in enumerate(new_sources.items(), 1):
        text += f"{i}. {title}\n🔗 {url}\n\n"
        
    text += "Проверьте файл `pending_sources.txt`."
    
    tg_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(tg_api, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)

# ==========================================
# 3. ОСНОВНАЯ ЛОГИКА РАЗВЕДЧИКА
# ==========================================
print("🚀 Разведчик начал сканирование Reddit...")
existing_domains = get_existing_domains()
found_external_urls = set()

# Шаг 1: Собираем внешние ссылки из профильных сообществ
for sub in SUBREDDITS:
    print(f"📡 Проверяем r/{sub}...")
    try:
        # Получаем 25 самых свежих постов (используем .json в конце URL для доступа к API)
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
        
        # Скачиваем через requests, маскируясь под браузер
        resp = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        
        # Проверяем статус-код (200 - всё ОК, 403/429 - нас заблокировали)
        if resp.status_code != 200:
            print(f"⚠️ Reddit заблокировал запрос (Код: {resp.status_code}). Пропускаем.")
            continue
            
        try:
            data = resp.json()
        except Exception as json_err:
            print(f"⚠️ Reddit вернул не JSON. Пропускаем. Ошибка: {json_err}")
            continue
        
        # Защита от неожиданной структуры JSON
        if not isinstance(data, dict) or 'data' not in data or 'children' not in data['data']:
             print("⚠️ Неожиданный формат ответа от Reddit. Пропускаем.")
             continue

        for child in data['data']['children']:
            post = child.get('data', {})
            post_url = post.get('url', '')
            
            # Пропускаем ссылки, ведущие на сам реддит (картинки, текстовые посты)
            if post_url and "reddit.com" not in post_url and "i.redd.it" not in post_url:
                domain = urlparse(post_url).netloc.replace("www.", "")
                
                # Если домен нам еще не известен
                if domain and domain not in existing_domains:
                    # Сохраняем корневой домен
                    base_url = f"{urlparse(post_url).scheme}://{urlparse(post_url).netloc}"
                    found_external_urls.add(base_url)
                    
        time.sleep(1) # Уважаем правила Reddit, не спамим запросами
    except Exception as e:
        print(f"❌ Ошибка парсинга r/{sub}: {e}")

# Шаг 2: Ищем RSS на найденных доменах и валидируем их
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
    # Сохраняем в файл-карантин
    with open(PENDING_FILE, "a", encoding="utf-8") as f:
        for title, url in valid_new_sources.items():
            f.write(f"# {title}\n{url}\n")
    
    # Отправляем сообщение в ТГ
    send_telegram_alert(valid_new_sources)
    print(f"🎉 Разведка завершена! Найдено {len(valid_new_sources)} новых источников.")
else:
    print("🤷‍♂️ Новых валидных источников сегодня не найдено.")
