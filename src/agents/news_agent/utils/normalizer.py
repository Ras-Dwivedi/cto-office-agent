def normalize_article(entry):
    """
    Convert RSS entry into normalized text for CF extraction
    """
    title = entry.get("title", "")
    summary = entry.get("summary", "")[:800]

    text = f"""
    Title: {title}
    Summary: {summary}
    """

    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "text": text.strip()
    }
