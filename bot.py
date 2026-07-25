import os

# 1. Настройки Telegram
# Скрипт будет брать значения из секретов GitHub
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('CHAT_ID')

import feedparser
import requests
import os
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
keywords = ['ar', 'phygital', 'audio', 'immersive', 'xr', 'augmented reality', 'spatial audio', 'immsersive audio', 'mixed reality', 'phygital', 'spatial computing', 'interactive']
exceptions = ['vr', 'virtual reality']

# Обновленные списки слов
keywords = ['ar', 'phygital', 'audio', 'immersive', 'xr', 'interactive']
exceptions = ['vr', 'virtual reality']

# ... внутри цикла, где бот перебирает новые статьи ...
title_lower = article.title.lower()
summary_lower = article.summary.lower() # Если вы проверяете и текст новости

# Условие 1: Ищем хотя бы одно совпадение по ключевым словам
has_keyword = any(word in title_lower or word in summary_lower for word in keywords)

# Условие 2: Ищем совпадения по стоп-словам
has_exception = any(exc in title_lower or exc in summary_lower for exc in exceptions)

# Применяем оператор and (есть нужное слово И нет стоп-слова)
if has_keyword and not has_exception:
    # Код отправки сообщения в Telegram
    print(f"Отправляем: {article.title}")
else:
    print(f"Пропускаем: {article.title}")


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

        # Отладочная печать: смотрим, какие новые статьи дошли до проверки
        print("🔍 Проверяем:", article.title)

        title_lower = article.title.lower()
        summary_lower = getattr(article, 'summary', '').lower()

        for word in keywords:
            if word in title_lower or word in summary_lower:
                translated_title = translator.translate(article.title)

                message_text = (
                    f"📰 Найдено по тегу #{word}\n\n"
                    f"🇷🇺 {translated_title}\n"
                    f"🇬🇧 {article.title}\n\n"
                    f"🔗 {article.link}"
                )

                tg_api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                requests.post(tg_api, data={"chat_id": chat_id, "text": message_text})

                with open(history_file, "a") as file:
                    file.write(article.link + "\n")

                sent_links.append(article.link)
                break

print("Проверка завершена!")
