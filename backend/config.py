"""Configuration settings for IASW backend."""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./iasw.db")

# File storage
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Logging
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = LOG_DIR / "audit.jsonl"

# LLM Provider configuration
# Options: "gemini", "groq", "ollama"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Gemini configuration (free tier)
# gemini-1.5-flash: 1500 req/day free | gemini-2.0-flash: 1500 req/day free
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

# Groq configuration (free tier - llama3 via Groq cloud)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# OCR Provider configuration
# Options: "gemini_vision" (handles handwriting + multilingual), "tesseract" (typed text only)
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "gemini_vision")

# Tesseract language (used when OCR_PROVIDER=tesseract)
# Examples: "eng", "hin+eng", "tam+eng", "urd+eng"
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "eng")

# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    "auto_approve": 0.90,
    "manual_review": 0.70,
    "auto_reject": 0.40,
}

# API settings
API_PREFIX = "/api/v1"
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Request ID prefix
REQUEST_ID_PREFIX = "REQ"
