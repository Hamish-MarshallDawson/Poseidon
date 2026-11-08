"""Settings from the repo-root .env (see the root .env.example). An optional backend/.env wins over it."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")          # optional per-backend overrides; load_dotenv never overrides, so this wins
load_dotenv(ROOT.parent / ".env")   # the one root .env per machine

AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY", "")
AISSTREAM_URL = os.getenv("AISSTREAM_URL", "wss://stream.aisstream.io/v0/stream")
# (lon, lat) corners, the 06 order. World by default; the Baltic is [[19,54],[31,61]].
AIS_BBOX = json.loads(os.getenv("AIS_BBOX") or "[[-180,-90],[180,90]]")
TIGER_DATABASE_URL = os.getenv("TIGER_DATABASE_URL", "")
DATA_DIR = ROOT / os.getenv("DATA_DIR", "data")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")]
STALE_AFTER_S = int(os.getenv("STALE_AFTER_S", "1800"))
# Digitraffic (Fintraffic, Finnish waters) live AIS over MQTT, merged with AISStream. On unless DIGITRAFFIC=0.
DIGITRAFFIC = os.getenv("DIGITRAFFIC", "1").strip().lower() not in ("0", "false", "no", "off")   # drop a ship from the map after this long silent

# Auth0: with DOMAIN and AUDIENCE set, /ws needs a valid access token. Unset means no login (local dev only).
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_ISSUER = os.getenv("AUTH0_ISSUER", "")   # default https://<AUTH0_DOMAIN>/

# Live predictor and graders (dvm/predict, #121). Off unless PREDICT=1. Without a champion in PREDICT_MODEL_DIR it
# runs the baselines, so the ledger and the graders work from the start.
PREDICT = os.getenv("PREDICT", "0").strip().lower() in ("1", "true", "yes", "on")
PREDICT_MODEL_DIR = Path(os.getenv("PREDICT_MODEL_DIR") or ROOT / "data" / "models")
PREDICT_INTERVAL_S = float(os.getenv("PREDICT_INTERVAL_S", "300"))
PREDICT_SAMPLE = int(os.getenv("PREDICT_SAMPLE", "150"))   # active ships per cycle (route + go-dark)
