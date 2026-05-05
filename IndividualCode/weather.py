import requests
from datetime import datetime, timedelta

# ✅ Open-Meteo — 100% FREE, no API key needed
# Weather history from 1940 | AQI history from 2022

WEATHER_URL   = "https://archive-api.open-meteo.com/v1/archive"
AQI_URL       = "https://air-quality-api.open-meteo.com/v1/air-quality"


# ─────────────────────────────────────────
#  FETCH weather for date range
# ─────────────────────────────────────────
def fetch_weather(lat, lon, start_date, end_date):
    params = {
        "latitude"   : lat,
        "longitude"  : lon,
        "start_date" : start_date,
        "end_date"   : end_date,
        "daily"      : [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "windspeed_10m_max",
            "relative_humidity_2m_max",
            "relative_humidity_2m_min",
            "weathercode",
        ],
        "timezone"        : "auto",
        "temperature_unit": "celsius",
        "windspeed_unit"  : "ms",
    }
    try:
        res  = requests.get(WEATHER_URL, params=params)
        data = res.json()
        if "error" in data:
            print(f"Weather API Error: {data['reason']}")
            return None
        return data["daily"]
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None


# ─────────────────────────────────────────
#  FETCH AQI for date range
# ─────────────────────────────────────────
def fetch_aqi(lat, lon, start_date, end_date):
    params = {
        "latitude"   : lat,
        "longitude"  : lon,
        "start_date" : start_date,
        "end_date"   : end_date,
        "hourly"     : [
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "us_aqi",
            "us_aqi_pm2_5",
            "us_aqi_pm10",
            "european_aqi",
            "dust",
            "uv_index",
        ],
        "timezone": "auto",
    }
    try:
        res  = requests.get(AQI_URL, params=params)
        data = res.json()
        if "error" in data:
            print(f"AQI API Error: {data['reason']}")
            return None
        return data["hourly"]
    except Exception as e:
        print(f"AQI fetch error: {e}")
        return None


# ─────────────────────────────────────────
#  Aggregate hourly AQI → daily averages
# ─────────────────────────────────────────
def aggregate_aqi_daily(hourly, dates):
    """
    Takes hourly AQI data and returns daily averages
    keyed by date string (YYYY-MM-DD).
    """
    daily = {}

    for i, ts in enumerate(hourly["time"]):
        date = ts[:10]   # extract YYYY-MM-DD from "2024-01-15T00:00"
        if date not in dates:
            continue
        if date not in daily:
            daily[date] = {
                "us_aqi"           : [],
                "european_aqi"     : [],
                "pm2_5"            : [],
                "pm10"             : [],
                "no2"              : [],
                "so2"              : [],
                "ozone"            : [],
                "co"               : [],
                "dust"             : [],
                "uv_index"         : [],
            }
        def add(key, field):
            v = hourly[field][i]
            if v is not None:
                daily[date][key].append(v)

        add("us_aqi",       "us_aqi")
        add("european_aqi", "european_aqi")
        add("pm2_5",        "pm2_5")
        add("pm10",         "pm10")
        add("no2",          "nitrogen_dioxide")
        add("so2",          "sulphur_dioxide")
        add("ozone",        "ozone")
        add("co",           "carbon_monoxide")
        add("dust",         "dust")
        add("uv_index",     "uv_index")

    # Average each list
    averaged = {}
    for date, fields in daily.items():
        averaged[date] = {
            k: round(sum(v) / len(v), 1) if v else None
            for k, v in fields.items()
        }
    return averaged


# ─────────────────────────────────────────
#  Label helpers
# ─────────────────────────────────────────
def us_aqi_label(aqi):
    if aqi is None:      return "N/A"
    if aqi <= 50:        return "Good ✅"
    if aqi <= 100:       return "Moderate 🟡"
    if aqi <= 150:       return "Sensitive 🟠"
    if aqi <= 200:       return "Unhealthy 🔴"
    if aqi <= 300:       return "Very Unhealthy 🟣"
    return                      "Hazardous ☠️"

def eu_aqi_label(aqi):
    if aqi is None:      return "N/A"
    if aqi <= 20:        return "Good ✅"
    if aqi <= 40:        return "Fair 🟢"
    if aqi <= 60:        return "Moderate 🟡"
    if aqi <= 80:        return "Poor 🟠"
    if aqi <= 100:       return "Very Poor 🔴"
    return                      "Extremely Poor ☠️"

def weather_label(code):
    codes = {
        0: "Clear ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
        45: "Fog 🌫️", 48: "Icy fog 🌫️",
        51: "Light drizzle 🌦️", 53: "Drizzle 🌦️", 55: "Heavy drizzle 🌧️",
        61: "Light rain 🌧️", 63: "Rain 🌧️", 65: "Heavy rain 🌧️",
        71: "Light snow 🌨️", 73: "Snow 🌨️", 75: "Heavy snow ❄️",
        80: "Showers 🌦️", 81: "Heavy showers 🌧️", 82: "Violent showers ⛈️",
        95: "Thunderstorm ⛈️", 96: "Thunderstorm+hail ⛈️",
    }
    return codes.get(code, f"Code {code}")

def fmt(v, unit="", decimals=1):
    return f"{round(v, decimals)}{unit}" if v is not None else "N/A"


# ─────────────────────────────────────────
#  GENERATE date list between two dates
# ─────────────────────────────────────────
def date_range(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((end - start).days + 1)]


# ─────────────────────────────────────────
#  MAIN: fetch + display range
# ─────────────────────────────────────────
def display_range(lat, lon, start_date, end_date):
    dates = date_range(start_date, end_date)
    total = len(dates)

    print(f"\n{'='*70}")
    print(f"  Weather + AQI Report  |  {start_date} → {end_date}  ({total} days)")
    print(f"  Location: {lat}, {lon}")
    print(f"{'='*70}")

    print("\n[Fetching weather data...]")
    weather = fetch_weather(lat, lon, start_date, end_date)

    print("[Fetching AQI data...]")
    aqi_hourly = fetch_aqi(lat, lon, start_date, end_date)

    if not weather or not aqi_hourly:
        print("Failed to fetch data.")
        return

    aqi_daily = aggregate_aqi_daily(aqi_hourly, set(dates))

    # ── Header row ──
    print(f"\n{'─'*70}")
    print(f"{'Date':<12} {'Condition':<20} {'Temp°C':>9} {'Rain mm':>8} {'Humidity%':>10} {'US AQI':>7} {'EU AQI':>7} {'PM2.5':>7} {'PM10':>6}")
    print(f"{'─'*70}")

    for i, date in enumerate(dates):
        # Weather values
        wcode  = weather["weathercode"][i]
        tmax   = weather["temperature_2m_max"][i]
        tmin   = weather["temperature_2m_min"][i]
        tmean  = weather["temperature_2m_mean"][i]
        rain   = weather["precipitation_sum"][i]
        hmax   = weather["relative_humidity_2m_max"][i]
        hmin   = weather["relative_humidity_2m_min"][i]

        temp_str = f"{fmt(tmin)}–{fmt(tmax)}" if tmin and tmax else fmt(tmean)
        hum_str  = f"{fmt(hmin,decimals=0)}–{fmt(hmax,decimals=0)}"

        # AQI values
        aqi = aqi_daily.get(date, {})
        us  = aqi.get("us_aqi")
        eu  = aqi.get("european_aqi")
        pm25= aqi.get("pm2_5")
        pm10= aqi.get("pm10")

        print(f"{date:<12} {weather_label(wcode):<20} {temp_str:>9} {fmt(rain,'mm'):>8} {hum_str:>10} {fmt(us,decimals=0):>7} {fmt(eu,decimals=0):>7} {fmt(pm25,'μg'):>8} {fmt(pm10,'μg'):>7}")

    # ── Detailed breakdown per day ──
    print(f"\n\n{'='*70}")
    print(f"  DETAILED DAILY BREAKDOWN")
    print(f"{'='*70}")

    for i, date in enumerate(dates):
        aqi = aqi_daily.get(date, {})
        us  = aqi.get("us_aqi")
        eu  = aqi.get("european_aqi")

        wcode = weather["weathercode"][i]
        tmax  = weather["temperature_2m_max"][i]
        tmin  = weather["temperature_2m_min"][i]
        wind  = weather["windspeed_10m_max"][i]
        rain  = weather["precipitation_sum"][i]
        hmax  = weather["relative_humidity_2m_max"][i]
        hmin  = weather["relative_humidity_2m_min"][i]

        print(f"\n  [{date}]  {weather_label(wcode)}")
        print(f"    Temperature   : {fmt(tmin)}°C – {fmt(tmax)}°C  (mean: {fmt(weather['temperature_2m_mean'][i])}°C)")
        print(f"    Precipitation : {fmt(rain)} mm")
        print(f"    Humidity      : {fmt(hmin,decimals=0)}% – {fmt(hmax,decimals=0)}%")
        print(f"    Wind (max)    : {fmt(wind)} m/s")
        print(f"    US AQI        : {fmt(us,decimals=0)}  →  {us_aqi_label(us)}")
        print(f"    EU AQI        : {fmt(eu,decimals=0)}  →  {eu_aqi_label(eu)}")
        print(f"    PM2.5         : {fmt(aqi.get('pm2_5'))} μg/m³")
        print(f"    PM10          : {fmt(aqi.get('pm10'))} μg/m³")
        print(f"    NO₂           : {fmt(aqi.get('no2'))} μg/m³")
        print(f"    SO₂           : {fmt(aqi.get('so2'))} μg/m³")
        print(f"    Ozone         : {fmt(aqi.get('ozone'))} μg/m³")
        print(f"    CO            : {fmt(aqi.get('co'))} μg/m³")
        print(f"    Dust          : {fmt(aqi.get('dust'))} μg/m³")
        print(f"    UV Index      : {fmt(aqi.get('uv_index'))}")
        print(f"    {'─'*50}")

    # ── Summary stats ──
    us_vals  = [aqi_daily[d]["us_aqi"]       for d in dates if d in aqi_daily and aqi_daily[d]["us_aqi"]       is not None]
    eu_vals  = [aqi_daily[d]["european_aqi"] for d in dates if d in aqi_daily and aqi_daily[d]["european_aqi"] is not None]
    tmp_vals = [weather["temperature_2m_mean"][i] for i, d in enumerate(dates) if weather["temperature_2m_mean"][i] is not None]
    rain_vals= [weather["precipitation_sum"][i]   for i, d in enumerate(dates) if weather["precipitation_sum"][i]   is not None]

    print(f"\n{'='*70}")
    print(f"  RANGE SUMMARY  ({total} days)")
    print(f"{'='*70}")
    if tmp_vals:
        print(f"  Avg Temperature   : {round(sum(tmp_vals)/len(tmp_vals),1)} °C")
        print(f"  Max Temperature   : {max(weather['temperature_2m_max'])} °C  on {dates[weather['temperature_2m_max'].index(max(weather['temperature_2m_max']))]}")
        print(f"  Min Temperature   : {min(weather['temperature_2m_min'])} °C  on {dates[weather['temperature_2m_min'].index(min(weather['temperature_2m_min']))]}")
    if rain_vals:
        print(f"  Total Rainfall    : {round(sum(rain_vals),1)} mm")
    if us_vals:
        avg_us = round(sum(us_vals)/len(us_vals),1)
        print(f"  Avg US AQI        : {avg_us}  →  {us_aqi_label(avg_us)}")
        print(f"  Max US AQI        : {max(us_vals)}  (worst day)")
        print(f"  Min US AQI        : {min(us_vals)}  (best day)")
    if eu_vals:
        avg_eu = round(sum(eu_vals)/len(eu_vals),1)
        print(f"  Avg EU AQI        : {avg_eu}  →  {eu_aqi_label(avg_eu)}")
    print(f"{'='*70}\n")


# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    lat        = float(input("Enter latitude        : "))
    lon        = float(input("Enter longitude       : "))
    start_date = input("Enter start date (YYYY-MM-DD) : ").strip()
    end_date   = input("Enter end date   (YYYY-MM-DD) : ").strip()

    display_range(lat, lon, start_date, end_date)