import requests
import xml.etree.ElementTree as ET
from datetime import datetime

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

def get_news_headlines(limit=5):
    """
    Fetches top news headlines from BBC News RSS feed.
    """
    try:
        url = "http://feeds.bbci.co.uk/news/rss.xml"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        news_items = []
        
        # Iterate over items in the channel
        for item in root.findall("./channel/item")[:limit]:
            title = item.find("title").text
            link = item.find("link").text
            news_items.append(f"• <{link}|{title}>")
            
        return news_items
    except Exception as e:
        print(f"Error fetching news: {e}")
        return ["Could not fetch news at this time."]

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
    news = get_news_headlines()
    news_str = "\n".join(news)
    
    message = (
        f"☀️ *Good Morning! Daily Briefing for {today}*\n\n"
        f"*Weather in Evanston:*\n{weather_str}\n\n"
        f"*Dressing Recommendation:*\n👗 {clothing}\n\n"
        f"*Major News:*\n{news_str}"
    )
    
    return message
