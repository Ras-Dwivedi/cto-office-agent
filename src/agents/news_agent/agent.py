import yaml

from src.db import get_collection
from src.agents.news_agent.utils.utils import hash_url, now
from src.agents.news_agent.utils.normalizer import normalize_article
from src.agents.news_agent.utils.cf_engine import find_or_create_news_cf
from src.agents.news_agent.utils.rss_reader import fetch_rss

news_articles = get_collection("news_articles")
edges_col = get_collection("news_cf_edges")


def load_feeds():
    with open("feeds.yaml", "r") as f:
        data = yaml.safe_load(f)
        return data.get("feeds", [])


def process_feed(feed):
    try:
        entries = fetch_rss(feed["url"])
    except Exception as e:
        print(f"❌ Failed to fetch feed {feed['name']}: {e}")
        return

    for entry in entries:
        url = entry.get("link")
        if not url:
            continue

        url_hash = hash_url(url)

        # Deduplication
        if news_articles.find_one({"hash": url_hash}):
            continue

        article_doc = {
            "url": url,
            "hash": url_hash,
            "title": entry.get("title"),
            "source": feed.get("name"),
            "published_date": entry.get("published"),
            "fetched_at": now(),
            "processed": False
        }

        news_articles.insert_one(article_doc)

        # Normalize → CF
        normalized = normalize_article(entry)
        cf_id = find_or_create_news_cf(normalized)

        # Link CF ↔ Article
        edges_col.insert_one({
            "cf_id": cf_id,
            "article_url": url,
            "published_date": entry.get("published"),
            "linked_at": now(),
            "source": feed.get("name")
        })

        # Mark processed
        news_articles.update_one(
            {"hash": url_hash},
            {"$set": {"processed": True}}
        )


def main():
    feeds = load_feeds()
    if not feeds:
        print("⚠️ No feeds configured")
        return

    for feed in feeds:
        process_feed(feed)

    print("📰 News CF ingestion completed")


if __name__ == "__main__":
    main()
