"""Settings from backend/.env (see .env.example)."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY", "")
AISSTREAM_URL = os.getenv("AISSTREAM_URL", "wss://stream.aisstream.io/v0/stream")
# (lon, lat) corners, the 06 order. World by default; the Baltic is [[19,54],[31,61]].
AIS_BBOX = json.loads(os.getenv("AIS_BBOX") or "[[-180,-90],[180,90]]")
TIGER_DATABASE_URL = os.getenv("TIGER_DATABASE_URL", "")
DATA_DIR = ROOT / os.getenv("DATA_DIR", "data")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")]
STALE_AFTER_S = int(os.getenv("STALE_AFTER_S", "1800"))   # drop a ship from the map after this long silent

# Milestone 2: Auth0 access-token validation on /ws and the API (unused until then).
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
