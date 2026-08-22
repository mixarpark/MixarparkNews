import os
import re
import requests
import feedparser
import pdfplumber
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# ==========================================
# 1. КОНФИГУРАЦИЯ И НАСТРОЙКИ
# ==========================================
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

FOLDER_PATH = "library_files"
SOURCE_LINKS_FILE = "source_links.txt"
HISTORY_FILE = "sent_articles.txt"

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

# Сверхбыстрая компиляция \b для поиска точных слов (исключает "darts")
KW_PATTERN = re.compile(rf"\b({'|'.join(map(re.escape, KEYWORDS))})\b", re.IGNORECASE)
EXC_PATTERN = re.compile(rf"\b({'|'.join(map(re.escape, EXCEPTIONS))})\b", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

translator = GoogleTranslator(source='auto', target='ru')

# ==========================================
# 2. ФУНКЦИИ ИЗВЛЕЧЕНИЯ И ОТПРАВКИ
# ==========================================
def extract_links_from_pdf(file_path):
    found_urls = set()
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    found_urls.update(re.findall(r"https?://[^\s\)]+", text))
    except Exception as e:
        print(f"❌ Ошибка PDF {file_path}: {e}")
    return found_urls

def extract_links_from_txt(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return set(re.findall(r"https?://[^\s\)]+", file.read()))
    except Exception as e:
        print(f"❌ Ошибка TXT {file_path}: {e}")
        return set()

def send_to_telegram(title, url, keyword):
    try:
        translated_title = translator.translate(title)
    except:
        translated_title = title 

    hashtag = f"#{keyword.replace(' ', '_').replace('-', '_')}"
    message_text = f"📰 Найдено по тегу {hashtag}\n\n🇷🇺 {translated_title}\n🇬🇧 {title}\n\n🔗 {url}"
    
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": message_text}, timeout=10)
    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}")

# ==========================================
# 3. ПОДГОТОВКА ИСТОЧНИКОВ (СБОР БАЗЫ)
# ==========================================
all_links = set()

# А. Сначала берем то, что нашел Разведчик (чтобы не стереть!)
if os.path.exists(SOURCE_LINKS_FILE):
    with open(SOURCE_LINKS_FILE, "r", encoding="utf-8") as f:
        all_links.update(f.read().splitlines())

# Б. Затем добавляем свежие ссылки из ручных файлов библиотеки
if os.path.exists(FOLDER_PATH):
    print(f"📁 Проверяем папку {FOLDER_PATH}...")
    for file_name in os.listdir(FOLDER_PATH):
        full_path = os.path.join(FOLDER_PATH, file_name)
        if file_name.lower().endswith(".pdf"):
            all_links.update(extract_links_from_pdf(full_path))
        elif file_name.lower().endswith(".txt"):
            all_links.update(extract_links_from_txt(full_path))

# В. Сохраняем объединенную базу без потери данных
with open(SOURCE_LINKS_FILE, "w", encoding="utf-8") as f:
    for link in sorted(all_links):
        if link.strip():
            f.write(link.strip() + "\n")

print(f"✅ База сформирована. Всего ссылок для проверки: {len(all_links)}")

# ==========================================
# 4. ПОИСК, ФИЛЬТРАЦИЯ И ОТПРАВКА НОВОСТЕЙ
# ==========================================
sent_links = set()
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as file:
        sent_links = set(file.read().splitlines())

print("\n🚀 Начинаем проверку сайтов и RSS-лент...")

for url in all_links:
    if not url.strip(): continue
    print(f"📡 Подключаемся к: {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            print(f"⚠️ Отклонено (Код {response.status_code}).")
            continue
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"⚠️ Ошибка сети/таймаут: {e}")
        continue

    # ================= ЛОГИКА 1: ВЕБ-СТРАНИЦЫ =================
    if not feed.entries:
        if url in sent_links:
            print(f"⏭️ Пропускаем: {url} (уже в истории)")
            continue
            
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Ищем только в заголовках и абзацах (игнорируем подвалы и меню)
            text_elements = soup.find_all(['title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'])
            clean_text = ' '.join(elem.get_text(separator=' ', strip=True) for elem in text_elements).lower()
            
            match_kw = KW_PATTERN.search(clean_text)
            match_exc = EXC_PATTERN.search(clean_text)
            
            print(f"🤖 Анализ страницы | Ключи: {bool(match_kw)} | Исключения: {bool(match_exc)}")
            
            if match_kw and not match_exc:
                page_title = soup.title.string.strip() if soup.title and soup.title.string else url
                found_word = match_kw.group(1).lower()
                
                print(f"✅ Отправляем: {page_title}")
                send_to_telegram(page_title, url, found_word)
                
                with open(HISTORY_FILE, "a", encoding="utf-8") as file:
                    file.write(url + "\n")
                sent_links.add(url)
                
        except Exception as e:
            print(f"⚠️ Ошибка HTML парсинга {url}: {e}")

    # ================= ЛОГИКА 2: RSS-ЛЕНТЫ =================
    else:
        for article in feed.entries:
            link = getattr(article, 'link', '')
            if not link or link in sent_links:
                continue
                
            title = getattr(article, 'title', '')
            summary = getattr(article, 'summary', '')
            combined_text = f"{title} {summary}".lower()
            
            match_kw = KW_PATTERN.search(combined_text)
            match_exc = EXC_PATTERN.search(combined_text)
            
            print(f"🤖 Анализ RSS: {title} | Ключи: {bool(match_kw)} | Искл: {bool(match_exc)}")
            
            if match_kw and not match_exc:
                found_word = match_kw.group(1).lower()
                print(f"✅ Отправляем RSS: {title}")
                
                send_to_telegram(title, link, found_word)
                
                with open(HISTORY_FILE, "a", encoding="utf-8") as file:
                    file.write(link + "\n")
                sent_links.add(link)

print("🎉 Проверка успешно завершена!")
