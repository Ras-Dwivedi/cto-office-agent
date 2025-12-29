import os

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

EMAIL_POLL_SECONDS = int(os.getenv("EMAIL_POLL_SECONDS", 60))
EMAIL_SLEEP_TIME__IN_HOURS = 2
EMAIL_PROCESSING_BATCH_SIZE = 10
POMODORO_MINUTES = 25
MAILBOX= "PRIMARY"