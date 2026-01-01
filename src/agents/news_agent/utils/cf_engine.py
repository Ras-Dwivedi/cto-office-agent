from utils import now
from src.db import get_collection
from src.agents.news_agent.utils.embedding import embed_text
from src.agents.news_agent.utils.utils import cosine_similarity

SIM_THRESHOLD = 0.82

news_cf_col = get_collection("news_contexts")
edges_col = get_collection("news_cf_edges")

def find_or_create_news_cf(normalized):
    embedding = embed_text(normalized["text"])

    candidates = list(news_cf_col.find({"cf_type": "NEWS"}))

    best_cf = None
    best_score = 0.0

    for cf in candidates:
        score = cosine_similarity(embedding, cf["embedding"])
        if score > best_score:
            best_cf = cf
            best_score = score

    if best_cf and best_score >= SIM_THRESHOLD:
        news_cf_col.update_one(
            {"_id": best_cf["_id"]},
            {
                "$inc": {"article_count": 1},
                "$set": {"last_seen_at": now()}
            }
        )
        return best_cf["_id"]

    # Create new CF
    cf_doc = {
        "cf_type": "NEWS",
        "title": normalized["title"],
        "abstract": normalized["summary"][:300],
        "keywords": [],
        "embedding": embedding,
        "article_count": 1,
        "confidence": 1.0,
        "created_at": now(),
        "last_seen_at": now()
    }

    return news_cf_col.insert_one(cf_doc).inserted_id
