import requests
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime

SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3.1-Terminus"  # Using DeepSeek V3 as requested/appropriate

def get_weather_evanston():
    """
    Fetches weather for Evanston, IL using Open-Meteo API.
    Returns a dictionary with weather details.
    """
    try:
        # Evanston coordinates: 42.0451, -87.6877
        url = "https://api.open-meteo.com/v1/forecast?latitude=42.0451&longitude=-87.6877&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&current_weather=true&timezone=America%2FChicago"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current_weather", {})
        daily = data.get("daily", {})
        
        # Get today's forecast (index 0)
        temp_max = daily["temperature_2m_max"][0]
        temp_min = daily["temperature_2m_min"][0]
        precip_prob = daily["precipitation_probability_max"][0]
        weather_code = daily["weathercode"][0]
        current_temp = current.get("temperature")
        
        return {
            "current_temp": current_temp,
            "max_temp": temp_max,
            "min_temp": temp_min,
            "precip_prob": precip_prob,
            "weather_code": weather_code
        }
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return None

def get_clothing_recommendation(weather_data):
    """
    Returns a clothing recommendation based on weather data.
    """
    if not weather_data:
        return "Could not fetch weather data, so wear whatever you feel like!"
    
    temp = weather_data["max_temp"]
    precip = weather_data["precip_prob"]
    code = weather_data["weather_code"]
    
    recommendation = []
    
    # Temperature based
    if temp < 0:
        recommendation.append("It's freezing! Wear a heavy winter coat, scarf, gloves, and a hat.")
    elif temp < 10:
        recommendation.append("It's cold. Wear a warm coat and maybe a scarf.")
    elif temp < 20:
        recommendation.append("It's chilly. A jacket or a sweater should be good.")
    elif temp < 25:
        recommendation.append("It's pleasant. A light jacket or long sleeves.")
    else:
        recommendation.append("It's warm! T-shirt and shorts weather.")
        
    # Rain/Snow based (WMO Weather interpretation codes)
    # 0-3: Clear/Cloudy, 51-67: Drizzle/Rain, 71-77: Snow, 80-82: Showers, 95-99: Thunderstorm
    is_raining = (51 <= code <= 67) or (80 <= code <= 82) or (95 <= code <= 99)
    is_snowing = (71 <= code <= 77)
    
    if is_raining or precip > 40:
        recommendation.append("Don't forget an umbrella ☂️, it might rain.")
    elif is_snowing:
        recommendation.append("It might snow ❄️, wear waterproof shoes.")
        
    return " ".join(recommendation)

def get_raw_news_headlines():
    """
    Fetches raw news headlines from multiple BBC News RSS feeds.
    Returns a list of dictionaries with title and link.
    """
    feeds = [
        "http://feeds.bbci.co.uk/news/rss.xml",            # Top Stories
        "http://feeds.bbci.co.uk/news/world/rss.xml",      # World
        "http://feeds.bbci.co.uk/news/business/rss.xml",   # Business
        "http://feeds.bbci.co.uk/news/technology/rss.xml"  # Technology
    ]
    
    all_news = []
    seen_titles = set()
    
    for url in feeds:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue
                
            root = ET.fromstring(response.content)
            # Get top 5 from each feed
            for item in root.findall("./channel/item")[:5]:
                title = item.find("title").text
                link = item.find("link").text
                
                if title not in seen_titles:
                    all_news.append({"title": title, "link": link})
                    seen_titles.add(title)
        except Exception as e:
            print(f"Error fetching news from {url}: {e}")
            
    return all_news

def organize_news_with_ai(news_items):
    """
    Uses SiliconFlow API to organize and rank news.
    """
    if not SILICONFLOW_API_KEY:
        # Fallback if no API key
        return "\n".join([f"• <{item['link']}|{item['title']}>" for item in news_items[:5]])

    news_text = "\n".join([f"- {item['title']} ({item['link']})" for item in news_items])
    
    prompt = f"""
    You are a professional news editor. I will provide a list of news headlines with links.
    Your task is to select the most important stories and organize them into three categories:
    
    1. 🌍 Global News (Ranked by importance)
    2. 💰 Economic News
    3. 🤖 Tech News
    
    For each category, select the top 3-5 most relevant stories from the list.
    Format the output as a clean Slack message using mrkdwn.
    Use bullet points with the format: • <Link|Title>
    Do not make up news. Only use the provided list.
    If a category has no relevant news in the list, you can skip it or state "No major updates".
    
    Here is the news list:
    {news_text}
    """
    
    payload = {
        "model": SILICONFLOW_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful news assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(SILICONFLOW_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error calling SiliconFlow API: {e}")
        # Fallback
        return "\n".join([f"• <{item['link']}|{item['title']}>" for item in news_items[:5]])

def generate_daily_briefing():
    """
    Generates the full daily briefing message.
    """
    # Date
    today = datetime.now().strftime("%A, %B %d, %Y")
    
    # Weather
    weather = get_weather_evanston()
    if weather:
        weather_str = f"🌡️ *Current:* {weather['current_temp']}°C | *High:* {weather['max_temp']}°C | *Low:* {weather['min_temp']}°C"
    else:
        weather_str = "Weather data unavailable."
        
    # Clothing
    clothing = get_clothing_recommendation(weather)
    
    # News
    raw_news = get_raw_news_headlines()
    if raw_news:
        news_section = organize_news_with_ai(raw_news)
    else:
        news_section = "Could not fetch news at this time."
    
    message = (
        f"☀️ *Good Morning! Daily Briefing for {today}*\n\n"
        f"*Weather in Evanston:*\n{weather_str}\n\n"
        f"*Dressing Recommendation:*\n👗 {clothing}\n\n"
        f"*Major News:*\n{news_section}"
    )
    
    return message
