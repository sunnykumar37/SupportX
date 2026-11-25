import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
KB_DIR = DATA_DIR / "knowledge_base"
STORAGE_DIR = ROOT_DIR / "storage"


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = os.getenv("SUPPORTX_DEMO_MODE", "true").lower() == "true"
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    confidence_threshold: float = float(os.getenv("SUPPORTX_CONFIDENCE_THRESHOLD", "0.60"))
    retrieval_threshold: float = float(os.getenv("SUPPORTX_RETRIEVAL_THRESHOLD", "0.34"))
    max_revision_attempts: int = int(os.getenv("SUPPORTX_MAX_REVISION_ATTEMPTS", "2"))


settings = Settings()