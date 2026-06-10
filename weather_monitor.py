import requests
import threading
from gi.repository import GLib
import time
import datetime

class WeatherMonitor(threading.Thread):
    def __init__(self, callback, city="Varanasi, India", lat=25.3333, lon=83.0):
        super().__init__(daemon=True)
        self.callback = callback
        self.city = city
        self.lat = lat
        self.lon = lon
        self.running = True
        self.force_update = False
        self.update_interval = 1800              

    def get_weather_icon(self, code):
        mapping = {
            0: "mdi.weather-sunny",
            1: "mdi.weather-partly-cloudy", 2: "mdi.weather-partly-cloudy", 3: "mdi.weather-cloudy",
            45: "mdi.weather-fog", 48: "mdi.weather-fog",
            51: "mdi.weather-rainy", 53: "mdi.weather-rainy", 55: "mdi.weather-rainy",
            61: "mdi.weather-pouring", 63: "mdi.weather-pouring", 65: "mdi.weather-pouring",
            71: "mdi.weather-snowy", 73: "mdi.weather-snowy", 75: "mdi.weather-snowy",
            80: "mdi.weather-rainy", 81: "mdi.weather-rainy", 82: "mdi.weather-rainy",
            95: "mdi.weather-lightning", 96: "mdi.weather-lightning", 99: "mdi.weather-lightning"
        }
        return mapping.get(code, "mdi.weather-cloudy")

    def get_weather_desc(self, code):
        mapping = {
            0: "Clear Sky",
            1: "Mainly Clear", 2: "Partly Cloudy", 3: "Cloudy",
            45: "Fog", 48: "Rime Fog",
            51: "Light Drizzle", 53: "Drizzle", 55: "Dense Drizzle",
            61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
            71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
            80: "Slight Showers", 81: "Showers", 82: "Violent Showers",
            95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"
        }
        return mapping.get(code, "Unknown")

    def run(self):
        time_since_last = self.update_interval                             
        while self.running:
            if time_since_last >= self.update_interval or self.force_update:
                try:
                    url = f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                    res = requests.get(url, timeout=10).json()
                    
                    if "current_weather" in res:
                        current = res["current_weather"]
                        daily = res.get("daily", {})
                        
                        t_max = int(daily["temperature_2m_max"][0]) if "temperature_2m_max" in daily else "--"
                        t_min = int(daily["temperature_2m_min"][0]) if "temperature_2m_min" in daily else "--"
                        
                        data = {
                            "city": self.city,
                            "temp": f"{int(current['temperature'])}°",
                            "desc": self.get_weather_desc(current["weathercode"]),
                            "icon": self.get_weather_icon(current["weathercode"]),
                            "high": f"{t_max}°",
                            "low": f"{t_min}°"
                        }
                        if self.callback: GLib.idle_add(self.callback, data)
                        self.force_update = False
                        time_since_last = 0
                except Exception as e:
                    print(f"Weather update error: {e}")
            
            time.sleep(1)                                      
            time_since_last += 1

    def stop(self):
        self.running = False
