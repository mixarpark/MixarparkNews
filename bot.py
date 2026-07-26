import os

# 1. Настройки Telegram
# Скрипт будет брать значения из секретов GitHub
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('CHAT_ID')

import feedparser
import requests
import os
import re
import pdfplumber


# Указываем путь к нашей новой папке
folder_path = "library_files"
# Получаем список всех файлов внутри
all_files = os.listdir(folder_path)
all_links = [] # Создаем пустой список для сбора ссылок со всех файлов

# 1. Перебираем файлы по очереди
for file_name in all_files:
    # Создаем полный путь к конкретному файлу
    full_path = os.path.join(folder_path, file_name)

    # 2. Открываем текущий файл в режиме чтения ("r")
    with open(full_path, "r", encoding="utf-8", errors="ignore") as file:
        text = file.read() # Читаем всё содержимое файла в переменную text

        # 3. Находим все ссылки в тексте файла
        found_urls = re.findall(r"https?://[^\s\)]+", text)
        
        # 4. Добавляем найденные ссылки в общий список
        all_links.extend(found_urls)



def extract_links_from_pdf(file_path):
    all_text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + " "
    except Exception as e:
        print(f"Ошибка чтения PDF {file_path}: {e}")
        
    found_urls = re.findall(r"https?://[^\s\)]+", all_text)
    return found_urls

def extract_links_from_txt(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            text = file.read()
            found_urls = re.findall(r"https?://[^\s\)]+", text)
            return found_urls
    except Exception as e:
        print(f"Ошибка чтения TXT {file_path}: {e}")
        return []

# Основная директория с библиотекой файлов
folder_name = "library_files"
all_links = []

# Проверяем наличие папки
if os.path.exists(folder_name):
    for file_name in os.listdir(folder_name):
        full_path = os.path.join(folder_name, file_name)
        

        # Обработка PDF-файлов
        if file_name.endswith(".pdf"):
            print(f"Обрабатываем PDF: {file_name}")
            links = extract_links_from_pdf(full_path)
            all_links.extend(links)
            
        # Обработка текстовых файлов
        elif file_name.endswith(".txt"):
            print(f"Обрабатываем TXT: {file_name}")
            links = extract_links_from_txt(full_path)
            all_links.extend(links)

# Удаляем дубликаты, оставляя только уникальные ссылки
unique_links = sorted(list(set(all_links)))

# Открываем новый файл в режиме записи ("w" - write)
output_file = "source_links.txt"
with open("source_links.txt", "w", encoding="utf-8") as file:
    for link in unique_links:
        # Записываем каждую ссылку и добавляем невидимый символ переноса строки
        file.write(link + "\n") 

# Сохраняем результат в файл, к которому потом обратится бот
output_file = "source_links.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for link in unique_links:
        f.write(link + "\n")



print(f"Найдено файлов: {len(all_files)}")
print("Список файлов:", all_files)
print(f"Всего найдено ссылок: {len(all_links)}")
print(f"Готово! Сохранено уникальных ссылок: {len(unique_links)}")

from deep_translator import GoogleTranslator

# Install missing libraries if not already installed
try:
    import feedparser
except ImportError:

    import feedparser
try:
    from deep_translator import GoogleTranslator
except ImportError:

    from deep_translator import GoogleTranslator


# 2. Настройки источников и фильтров
rss_urls = [
    "https://www.roadtovr.com/feed/",
    "https://uploadvr.com/feed/"
]

# Обновленные списки слов
keywords = ['ar', 'phygital', 'audio', 'immersive', 'xr', 'augmented reality', 'spatial audio', 'immsersive audio', 'mixed reality', 'phygital', 'spatial computing', 'interactive', 'smart glasses', 'ai']
exceptions = ['vr', 'virtual reality']


# 3. Загрузка истории
history_file = "sent_articles.txt"
if os.path.exists(history_file):
    with open(history_file, "r") as file:
        sent_links = file.read().splitlines()
else:
    sent_links = []

translator = GoogleTranslator(source='auto', target='ru')
print("Начинаем проверку лент...")

# 4. Поиск, перевод и отправка
for url in rss_urls:
    feed = feedparser.parse(url)

    for article in feed.entries:
        if article.link in sent_links:
            continue

        # Начало блока фильтрации (отступ 4 пробела от уровня for)
        title_lower = article.title.lower()
        summary_lower = article.summary.lower()
            
        # Проверяем ключевые слова и исключения сразу ВЕЗДЕ (и в заголовке, и в тексте)
        has_keyword = any(re.search(rf"\b{word}\b", title_lower) or re.search(rf"\b{word}\b", summary_lower) for word in keywords)
        has_exception = any(re.search(rf"\b{exc}\b", title_lower) or re.search(rf"\b{exc}\b", summary_lower) for exc in exceptions)


        # Выводим скрытые "мысли" бота в журнал:
        print(f"🤖 Анализ: {title_lower} | Ключевые: {has_keyword} | Исключения: {has_exception}")

        # Если НЕТ ключевых слов ИЛИ ЕСТЬ исключение -> пропускаем
        if not has_keyword or has_exception:
            print(f"Пропускаем: {article.title}")
            continue # 🛑 ВАЖНО: Прерываем работу с этой статьей и идем к следующей
            
        # Если код дошел сюда, значит статья идеальная (есть ключи, нет исключений)
        print(f"✅ Отправляем: {article.title}")
        
        # Находим точное слово для хештега с помощью регулярных выражений
        found_word = "news" # Значение по умолчанию
        for word in keywords:
            if re.search(rf"\b{word}\b", title_lower) or re.search(rf"\b{word}\b", summary_lower):
                found_word = word.replace(" ", "_") # Убираем пробелы для хештега (spatial audio -> #spatial_audio)
                break

        
        # Отправка в Telegram
        translated_title = translator.translate(article.title)
        
        message_text = (
            f"📰 Найдено по тегу #{found_word}\n\n"
            f"🇷🇺 {translated_title}\n"
            f"🇬🇧 {article.title}\n\n"
            f"🔗 {article.link}"
        )

        tg_api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(tg_api, data={"chat_id": chat_id, "text": message_text})

        # Сохраняем ссылку, чтобы не отправить повторно
        with open(history_file, "a") as file:
            file.write(article.link + "\n")
        sent_links.append(article.link)
                

print("Проверка завершена!")
