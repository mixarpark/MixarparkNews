import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from deep_translator import GoogleTranslator

# ==========================================
# 1. КОНФИГУРАЦИЯ И АВТОРИЗАЦИЯ
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

EXISTING_SOURCES_FILE = "source_links.txt"
REQ_TIMEOUT = 12

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# ==========================================
# 2. МАТРИЦА ЗАПРОСОВ (Phygital & Audio AR)
# ==========================================
SEARCH_QUERIES = [
    'phygital experience blog',
    'spatial audio news',
    'augmented reality smart glasses articles',
    'location based entertainment insights',
    'phygital retail case study',
    'smart city urban tech blog',
    'audio ar spatial computing pdf',
    'immersive marketing strategy pdf'
]

# 18 целевых языков для перевода запросов
TARGET_LANGUAGES = [
    'es', 'pt', 'it', 'id', 'vi', 'hi', 'ur', 'tr', 'ka', 
    'hy', 'kk', 'zh-CN', 'ru', 'de', 'fr', 'ar', 'ja', 'ko'
]

KEYWORDS = [
    'phygital', 'phygital experience', 'phygital business', 'phygital integration',
    'physical-digital', 'digital-physical', 'blended reality', 'blended experience',
    'omnichannel experience', 'seamless experience', 'location-based experience',
    'location-based entertainment', 'lbe', 'audio ar', 'audio augmented reality', 
    'spatial audio', 'immersive audio', '3d audio', 'binaural audio', 'directional audio', 
    'location-based audio', 'proximity audio', 'interactive audio', 'adaptive audio', 
    'audio guide', 'smart guide', 'sonic branding', 'augmented reality', 'mixed reality', 
    'spatial computing', 'spatial web', 'spatial mapping', 'smart glasses', 'ar glasses', 
    'wearable tech', 'webxr', 'location-based ar', 'digital twin', 'digital twin city', 
    'extended reality', 'xr', 'phygital marketing', 'phygital retail', 'ar marketing', 
    'ar advertising', 'virtual try-on', 'ar try-on', 'smart mirror', 'interactive packaging',
    'connected packaging', 'immersive retail', 'experiential marketing', 'virtual showroom', 
    'interactive billboard', 'digital out-of-home', 'dooh', 'smart tourism', 'ar tourism', 
    'smart destination', 'urban tech', 'smart city', 'connected city', 'digital guide', 
    'interactive map', 'wayfinding', 'urban ar', 'public space activation', 'spatial design', 
    'immersive design', 'product development', 'phygital product', 'ar developer', 'xr expert', 
    'spatial computing developer', 'phygital expert', 'immersive technology'
]

EXCEPTIONS = [
    'virtual reality', 'vr', 'fully virtual', 'vr headset', 'metaverse',
    'ai', 'artificial intelligence', 'machine learning', 'generative ai',
    'chatbot', 'automation', 'podcast', 'audiobook', 'music streaming', 
    'stereo audio', 'digital marketing', 'email marketing', 'influencer marketing', 
    'seo marketing'
]

KW_PATTERN = re.compile(rf"\b({'|'.join(map(re.escape, KEYWORDS))})\b", re.IGNORECASE)
EXC_PATTERN = re.compile(rf"\b({'|'.join(map(re.escape, EXCEPTIONS))})\b", re.IGNORECASE)

BLACKLIST_DOMAINS = {
    'youtube.com', 'facebook.com', 'twitter.com', 'x.com', 'instagram.com',
    'linkedin.com', 'wikipedia.org', 'amazon.com', 'reddit.com', 'pinterest.com',
    'tiktok.com', 'quora.com', 'medium.com', 'apple.com', 'spotify.com'
}

# ==========================================
# 3. ФУНКЦИИ ВАЛИДАЦИИ
# ==========================================
def get_existing_links():
    if not os.path.exists(EXISTING_SOURCES_FILE):
        return set()
    with open(EXISTING_SOURCES_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def find_rss_on_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for link in soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml', re.IGNORECASE)):
                href = link.get('href')
                if href: return urljoin(url, href)
    except: pass
    return None

def validate_rss(rss_url):
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=REQ_TIMEOUT)
        feed = feedparser.parse(resp.content)
        if not feed.entries: return False
        
        for entry in feed.entries[:10]:
            text = f"{getattr(entry, 'title', '')} {getattr(entry, 'summary', '')}"
            if KW_PATTERN.search(text) and not EXC_PATTERN.search(text):
                return True
    except: pass
    return False

def validate_web_page_or_doc(url, snippet=""):
    if snippet and KW_PATTERN.search(snippet) and not EXC_PATTERN.search(snippet):
        return True
    if url.lower().endswith('.pdf'):
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            page_text = soup.get_text(separator=' ')
            if KW_PATTERN.search(page_text) and not EXC_PATTERN.search(page_text):
                return True
    except: pass
    return False

def send_telegram_report(new_sources):
    if not new_sources or not BOT_TOKEN or not CHAT_ID: return
    text = (
        f"🕵️‍♂️ <b>Отчет Разведчика (Phygital & Audio AR)</b>\n\n"
        f"Глобальный поиск завершен. Добавлено в базу: <b>{len(new_sources)}</b> новых источников.\n"
        f"<i>Основной бот проверит их при следующем запуске.</i>"
    )
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"⚠️ Ошибка отправки отчета: {e}")

# ==========================================
# 4. ОСНОВНОЙ ЦИКЛ ПОИСКА (МУЛЬТИЯЗЫЧНЫЙ)
# ==========================================
print("🚀 Разведчик запускает глобальный мультиязычный поиск...")

if not SERPER_API_KEY:
    print("❌ Ошибка: SERPER_API_KEY не задан!")
    exit(1)

existing_links = get_existing_links()
discovered_items = [] 

for base_query in SEARCH_QUERIES:
    for lang in TARGET_LANGUAGES:
        try:
            translated_query = GoogleTranslator(source='en', target=lang).translate(base_query)
            print(f"📡 Поиск [{lang.upper()}]: {translated_query}")
            
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'},
                json={"q": translated_query, "num": 20, "hl": lang},
                timeout=REQ_TIMEOUT
            )
            
            if resp.status_code == 200:
                for item in resp.json().get('organic', []):
                    link = item.get('link', '')
                    snippet = item.get('snippet', '')
                    if link:
                        domain = urlparse(link).netloc.replace("www.", "")
                        if domain and not any(bl in domain for bl in BLACKLIST_DOMAINS) and link not in existing_links:
                            discovered_items.append((link, snippet))
                            
            time.sleep(1) # Пауза для защиты от лимитов переводчика
        except Exception as e:
            print(f"❌ Сбой API ({lang.upper()}): {e}")

print(f"🔍 Собрано кандидатов со всего мира: {len(discovered_items)}")

valid_new_sources = set()

for link, snippet in discovered_items:
    if link in existing_links or link in valid_new_sources: continue
    base_url = f"{urlparse(link).scheme}://{urlparse(link).netloc}"
    
    # Попытка 1: Ищем RSS
    rss_url = find_rss_on_page(base_url)
    if rss_url and rss_url not in existing_links:
        if validate_rss(rss_url):
            print(f"   [+] Добавлен RSS: {rss_url}")
            valid_new_sources.add(rss_url)
            existing_links.add(rss_url)
            continue
            
    # Попытка 2: Проверяем прямую страницу
    if validate_web_page_or_doc(link, snippet):
        print(f"   [+] Добавлена страница/PDF: {link}")
        valid_new_sources.add(link)
        existing_links.add(link)

if valid_new_sources:
    with open(EXISTING_SOURCES_FILE, "a", encoding="utf-8") as f:
        for url in valid_new_sources:
            f.write(f"{url}\n")
    send_telegram_report(valid_new_sources)
    print(f"🎉 Разведка завершена! Добавлено {len(valid_new_sources)} новых источников.")
else:
    print("🤷‍♂️ Новых валидных источников в этом цикле не найдено.")
