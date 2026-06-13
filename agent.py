import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import os

# --- НАСТРОЙКИ ---
DB_FILE = "charts.db"
REPORT_FILE = "ОТЧЕТ.md"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, country TEXT, position INT, track TEXT, artist TEXT)''')
    conn.commit()
    return conn

def get_wikipedia_summary(artist):
    """Получает краткую справку об артисте из Википедии без API-ключей"""
    try:
        url = f"https://ru.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={requests.utils.quote(artist)}&format=json"
        response = requests.get(url, headers={'User-Agent': 'MusicAgent/1.0'}, timeout=5).json()
        pages = response['query']['pages']
        for page_id in pages:
            if page_id != '-1':
                summary = pages[page_id]['extract']
                return summary[:200] + "..." if len(summary) > 200 else summary
    except:
        pass
    return "Информация не найдена."

def scrape_russia_top20():
    """Парсинг публичного чарта TopHit (Россия)"""
    url = "https://tophit.ru/ru/chart/top/youtube/russia"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    tracks = []
    # Находим строки таблицы чарта
    rows = soup.select('table.chart-table tbody tr')[:20]
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 3:
            pos = int(cols[0].text.strip())
            # В TopHit трек и артист часто в одном блоке, разделяем их
            full_title = cols[1].text.strip()
            parts = full_title.split(' - ')
            track = parts[0].strip() if len(parts) > 1 else full_title
            artist = parts[1].strip() if len(parts) > 1 else "Неизвестен"
            tracks.append({'pos': pos, 'track': track, 'artist': artist})
    return tracks

def scrape_global_top20():
    """Парсинг публичного чарта Kworb (Spotify Global)"""
    url = "https://kworb.net/spotify/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    tracks = []
    rows = soup.select('table.addsortable tbody tr')[:20]
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 3:
            pos = int(cols[0].text.strip())
            track = cols[1].text.strip()
            artist = cols[2].text.strip()
            tracks.append({'pos': pos, 'track': track, 'artist': artist})
    return tracks

def check_is_new(conn, country, track, artist):
    """Проверяет, был ли трек в чарте ранее"""
    c = conn.cursor()
    c.execute("SELECT 1 FROM history WHERE country=? AND track=? AND artist=?", (country, track, artist))
    return c.fetchone() is None

def generate_report(ru_tracks, global_tracks):
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    conn = init_db()
    
    md = f"# 🎵 Ежедневный отчет чартов ({today})\n\n"
    
    # --- РОССИЯ ---
    md += "## 🇷🇺 Россия (TopHit YouTube)\n"
    for t in ru_tracks:
        is_new = check_is_new(conn, 'RU', t['track'], t['artist'])
        new_badge = "🔥 **NEW** " if is_new else ""
        summary = get_wikipedia_summary(t['artist']) if is_new else ""
        summary_text = f"\n> _{summary}_" if summary else ""
        
        md += f"{new_badge}**#{t['pos']}** {t['track']} — *{t['artist']}*{summary_text}\n"
        
        # Сохраняем в историю
        c = conn.cursor()
        c.execute("INSERT INTO history (date, country, position, track, artist) VALUES (?, ?, ?, ?, ?)",
                  (today, 'RU', t['pos'], t['track'], t['artist']))
    
    md += "\n---\n\n"
    
    # --- МИР ---
    md += "## 🌍 Мир (Spotify Global via Kworb)\n"
    for t in global_tracks:
        is_new = check_is_new(conn, 'GLOBAL', t['track'], t['artist'])
        new_badge = "🔥 **NEW** " if is_new else ""
        summary = get_wikipedia_summary(t['artist']) if is_new else ""
        summary_text = f"\n> _{summary}_" if summary else ""
        
        md += f"{new_badge}**#{t['pos']}** {t['track']} — *{t['artist']}*{summary_text}\n"
        
        c = conn.cursor()
        c.execute("INSERT INTO history (date, country, position, track, artist) VALUES (?, ?, ?, ?, ?)",
                  (today, 'GLOBAL', t['pos'], t['track'], t['artist']))
    
    conn.commit()
    conn.close()
    return md

if __name__ == "__main__":
    print("Сбор данных...")
    ru_data = scrape_russia_top20()
    global_data = scrape_global_top20()
    
    print("Генерация отчета...")
    report = generate_report(ru_data, global_data)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    
    print("Готово! Отчет сохранен в", REPORT_FILE)
