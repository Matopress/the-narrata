"""Fetch 5-day forecasts for Kampala, East African, African and world cities into docs/weather.json.

Data: MET Norway Locationforecast (api.met.no), free for commercial use with credit
("Weather data from MET Norway"). Run on a schedule, not by every visitor, as their rules ask.
No pip packages needed.
"""
import json
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(__file__).parent / "docs" / "weather.json"
UA = "TheNarrata/1.0 (+https://github.com/Matopress/the-narrata)"  # MET asks callers to identify themselves

# (name, group, latitude, longitude, time zone)
CITIES = [
    ("Kampala", "East Africa", 0.3476, 32.5825, "Africa/Kampala"),
    ("Entebbe", "East Africa", 0.0512, 32.4637, "Africa/Kampala"),
    ("Jinja", "East Africa", 0.4244, 33.2041, "Africa/Kampala"),
    ("Nairobi", "East Africa", -1.2921, 36.8219, "Africa/Nairobi"),
    ("Mombasa", "East Africa", -4.0435, 39.6682, "Africa/Nairobi"),
    ("Dar es Salaam", "East Africa", -6.7924, 39.2083, "Africa/Dar_es_Salaam"),
    ("Kigali", "East Africa", -1.9441, 30.0619, "Africa/Kigali"),
    ("Addis Ababa", "East Africa", 9.0300, 38.7400, "Africa/Addis_Ababa"),
    ("Juba", "East Africa", 4.8594, 31.5713, "Africa/Juba"),
    ("Lagos", "Africa", 6.5244, 3.3792, "Africa/Lagos"),
    ("Cairo", "Africa", 30.0444, 31.2357, "Africa/Cairo"),
    ("Johannesburg", "Africa", -26.2041, 28.0473, "Africa/Johannesburg"),
    ("Cape Town", "Africa", -33.9249, 18.4241, "Africa/Johannesburg"),
    ("Accra", "Africa", 5.6037, -0.1870, "Africa/Accra"),
    ("Kinshasa", "Africa", -4.4419, 15.2663, "Africa/Kinshasa"),
    ("London", "World", 51.5072, -0.1276, "Europe/London"),
    ("New York", "World", 40.7128, -74.0060, "America/New_York"),
    ("Dubai", "World", 25.2048, 55.2708, "Asia/Dubai"),
    ("Mumbai", "World", 19.0760, 72.8777, "Asia/Kolkata"),
    ("Beijing", "World", 39.9042, 116.4074, "Asia/Shanghai"),
    ("Tokyo", "World", 35.6762, 139.6503, "Asia/Tokyo"),
]

DAYNIGHT = re.compile(r"_(day|night|polartwilight)$")


def get(lat: float, lon: float) -> dict:
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def process(payload: dict, tzname: str) -> dict:
    series = payload["properties"]["timeseries"]
    tz = ZoneInfo(tzname)
    first = series[0]["data"]
    block = first.get("next_1_hours") or first.get("next_6_hours") or first.get("next_12_hours") or {}
    now = {"temp": round(first["instant"]["details"]["air_temperature"], 1),
           "symbol": DAYNIGHT.sub("", block.get("summary", {}).get("symbol_code", ""))}

    days: dict = {}
    for entry in series:
        local = datetime.fromisoformat(entry["time"].replace("Z", "+00:00")).astimezone(tz)
        day = days.setdefault(local.date().isoformat(), {"temps": [], "midday": Counter(), "any": Counter()})
        day["temps"].append(entry["data"]["instant"]["details"]["air_temperature"])
        blk = entry["data"].get("next_6_hours")
        if blk:
            code = DAYNIGHT.sub("", blk["summary"]["symbol_code"])
            day["any"][code] += 1
            if 8 <= local.hour <= 17:
                day["midday"][code] += 1

    out = []
    for date in sorted(days)[:5]:
        d = days[date]
        counts = d["midday"] or d["any"]
        out.append({"date": date, "max": round(max(d["temps"]), 1), "min": round(min(d["temps"]), 1),
                    "symbol": counts.most_common(1)[0][0] if counts else ""})
    return {"now": now, "days": out}


def main() -> None:
    previous = {}
    if OUT.exists():
        try:
            previous = {c["name"]: c for c in json.loads(OUT.read_text(encoding="utf-8")).get("cities", [])}
        except (json.JSONDecodeError, KeyError):
            pass

    cities = []
    for name, group, lat, lon, tzname in CITIES:
        result = None
        for attempt in range(2):
            try:
                result = process(get(lat, lon), tzname)
                break
            except Exception as exc:
                print(f"{name}: attempt {attempt + 1} failed ({exc})")
                time.sleep(2)
        if result:
            cities.append({"name": name, "group": group, **result})
            print(f"OK    {name}")
        elif name in previous:
            cities.append(previous[name])  # keep the last good forecast rather than drop the city
            print(f"STALE {name}")
        time.sleep(0.4)  # be gentle with the free service

    if not cities:
        print("No weather data fetched; leaving weather.json unchanged.")
        return
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "cities": cities},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(cities)} cities")


if __name__ == "__main__":
    main()
