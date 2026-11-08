"""Load the repo-root .env once (GEMINI_API_KEY, TIGER_DATABASE_URL, ML_DATABASE_URL). Never print its values."""
from dotenv import load_dotenv

from ml import REPO

load_dotenv(REPO / ".env", override=False)
