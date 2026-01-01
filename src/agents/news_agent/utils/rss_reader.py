import requests
import xml.etree.ElementTree as ET

def fetch_rss(url: str):
    """
    Fetch and parse RSS feed without feedparser.
    Returns list of entries.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    items = []
    for item in root.findall(".//item"):
        entry = {
            "title": item.findtext("title"),
            "link": item.findtext("link"),
            "summary": item.findtext("description"),
            "published": item.findtext("pubDate")
        }
        items.append(entry)

    return items
