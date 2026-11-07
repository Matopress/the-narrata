"""Fetch news from RSS feeds, clean, dedupe, tag by region, and write docs/news.json.

Run:  pip install feedparser && python fetch_news.py
"""
import hashlib
import html
import json
import re
import sys
from calendar import timegm
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

ROOT = Path(__file__).parent
FEEDS = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "news.json"

KEEP_DAYS = 7          # drop stories older than this
MAX_ITEMS = 800        # cap the file size
SNIPPET_CHARS = 240
USER_AGENT = "NarrataBot/1.0 (+https://example.com/about)"  # put your real site here

# Keyword tagging. Checked in order: Uganda > East Africa > Africa.
UGANDA = ["uganda", "kampala", "museveni", "entebbe", "jinja", "gulu", "mbarara", "mbale",
          "ugandan", "bobi wine", "kyadondo", "uganda shilling", "ugx", "uwa ", "kcca"]
EAST_AFRICA = ["kenya", "nairobi", "mombasa", "tanzania", "dar es salaam", "dodoma", "zanzibar",
               "rwanda", "kigali", "burundi", "south sudan", "juba", "ethiopia", "addis ababa",
               "somalia", "mogadishu", "djibouti", "eritrea", "east africa", "eac", "congo", "drc"]
AFRICA = ["africa", "african", "nigeria", "lagos", "ghana", "accra", "south africa", "johannesburg",
          "cape town", "egypt", "cairo", "morocco", "algeria", "tunisia", "senegal", "sahel",
          "sudan", "khartoum", "zambia", "zimbabwe", "malawi", "mozambique", "angola", "namibia",
          "botswana", "cameroon", "ivory coast", "mali", "niger", "chad", "libya", "au summit",
          "african union", "afcon"]

CATEGORIES = {
    "Politics": ["election", "parliament", "president", "minister", "government", "court", "law",
                 "opposition", "campaign", "vote", "cabinet", "policy", "sanction"],
    "Business": ["economy", "bank", "shilling", "inflation", "trade", "investment", "market",
                 "budget", "tax", "oil", "coffee", "gdp", "company", "fuel", "price"],
    "Sports": ["football", "cranes", "afcon", "cricket", "athletics", "olympic", "goal", "match",
               "league", "rugby", "boxing", "fifa", "caf"],
    "Tourism": ["tourism", "safari", "gorilla", "national park", "lodge", "wildlife", "visitors",
                "hotel", "travel", "airline", "flight"],
    "Health": ["health", "hospital", "disease", "outbreak", "ebola", "malaria", "vaccine", "who "],
    "Tech": ["technology", "tech", "startup", "ai ", "internet", "mobile money", "digital", "cyber"],
}


def clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def snippet(entry) -> str:
    raw = entry.get("summary") or entry.get("description") or ""
    if not raw and entry.get("content"):
        raw = entry["content"][0].get("value", "")
    text = clean_text(raw)
    if len(text) > SNIPPET_CHARS:
        text = text[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"
    return text


def image(entry) -> str | None:
    for key in ("media_content", "media_thumbnail"):
        items = entry.get(key) or []
        if items and items[0].get("url"):
            return items[0]["url"]
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href")
    m = re.search(r'<img[^>]+src="([^"]+)"', entry.get("summary", "") or "")
    return m.group(1) if m else None


def published(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        if entry.get(key):
            return datetime.fromtimestamp(timegm(entry[key]), tz=timezone.utc)
    return datetime.now(timezone.utc)


def has_word(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def tag_region(title: str, summary: str, default: str) -> str:
    text = f" {title} {summary} ".lower()
    if has_word(text, UGANDA):
        return "Uganda"
    if has_word(text, EAST_AFRICA):
        return "East Africa"
    if has_word(text, AFRICA):
        return "Africa"
    return default


def tag_category(title: str, summary: str) -> str:
    text = f" {title} {summary} ".lower()
    for name, words in CATEGORIES.items():
        if has_word(text, words):
            return name
    return "General"


def normalize_title(title: str) -> str:
    # Google News appends " - Outlet"; strip it so the same story dedupes across feeds.
    title = re.sub(r"\s[-–|]\s[^-–|]{2,40}$", "", title)
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def split_outlet(title: str, feed_name: str) -> tuple[str, str]:
    """Google News titles end with ' - Outlet'. Use the real outlet as the source."""
    if feed_name.startswith("Google News"):
        m = re.match(r"^(.*)\s-\s([^-]{2,40})$", title)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return title, feed_name


def fetch_all() -> list[dict]:
    stories = []
    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"], agent=USER_AGENT)
        except Exception as exc:  # network or parse failure should never stop the run
            print(f"FAIL  {feed['name']}: {exc}", file=sys.stderr)
            continue
        entries = parsed.get("entries", [])
        print(f"{'OK  ' if entries else 'ZERO'}  {feed['name']}: {len(entries)} items")
        for e in entries:
            title = clean_text(e.get("title", ""))
            link = e.get("link")
            if not title or not link:
                continue
            title, source = split_outlet(title, feed["name"])
            summary = snippet(e)
            when = published(e)
            stories.append({
                "id": hashlib.sha1(normalize_title(title).encode()).hexdigest()[:16],
                "title": title,
                "source": source,
                "url": link,
                "published": when.isoformat(),
                "snippet": summary if normalize_title(summary) != normalize_title(title) else "",
                "image": image(e),
                "region": tag_region(title, summary, feed["region"]),
                "category": tag_category(title, summary),
            })
    return stories


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    existing = []
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8")).get("stories", [])
        except json.JSONDecodeError:
            pass

    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    merged: dict[str, dict] = {}
    # Existing first, fresh second: fresh wins, but a story keeps its best (non-empty) image.
    for story in existing + fetch_all():
        if datetime.fromisoformat(story["published"]) < cutoff:
            continue
        prev = merged.get(story["id"])
        if prev and not story.get("image"):
            story["image"] = prev.get("image")
        merged[story["id"]] = story

    stories = sorted(merged.values(), key=lambda s: s["published"], reverse=True)[:MAX_ITEMS]
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(),
        "stories": stories,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(stories)} stories to {OUT}")


if __name__ == "__main__":
    main()
