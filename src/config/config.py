import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

# IMAP
IMAP_HOST = os.getenv("IMAP_HOST")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# MongoDB
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASS = os.getenv("MONGO_PASS")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
DB_NAME = os.getenv("DB_NAME")

EMAIL_POLL_SECONDS = 120
EMAIL_SLEEP_TIME__IN_HOURS = 2
EMAIL_PROCESSING_BATCH_SIZE = 10
POMODORO_MINUTES = 25
MAILBOX= "PRIMARY"
EMAIL_PROCESSOR_VERSION=3
EXCLUDED_FOLDERS = {
    "Drafts",
    "Spam",
    "Trash",
    "Bin",
    "Junk",
    "Recommendations",
    "health conference",
    "appstores notification",
    "Digilocker",
    "Credit Card"
    "Archive",
    "hr.travel",
    "hr.leaves",
    "hr.keka",
    # "hr.misc HR",
    "Credit Card"
}

EXCLUDED_PREFIXES = (
    "Archives.",
    "Archive.",
    "Trash"
    "Trash."
)
CUTOFF_DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)
