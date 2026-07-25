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

# Обновленные списки слов
keywords = ['ar', 'phygital', 'audio', 'immersive', 'xr', 'augmented reality', 'spatial audio', 'immsersive audio', 'mixed reality', 'phygital', 'spatial computing', 'interactive']
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

        # Отладочная печать: смотрим, какие новые статьи дошли до проверки
        print("🔍 Проверяем:", article.title)

            
        # Начало блока фильтрации (отступ 4 пробела от уровня for)
        title_lower = article.title.lower()
        summary_lower = article.summary.lower() # Раскомментировать при необходимости
            
        has_keyword = any(word in title_lower for word in keywords)
        has_exception = any(exc in title_lower for exc in exceptions)
            
        # Оператор if находится на том же уровне (4 пробела)
        if has_keyword and not has_exception:
            # Команды внутри if получают дополнительный отступ (+4 пробела)
            print(f"Отправляем: {article.title}")
        else:
            print(f"Пропускаем: {article.title}")


        
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
