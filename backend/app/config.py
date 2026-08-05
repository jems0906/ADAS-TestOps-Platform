from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = os.getenv("APP_NAME", "ADAS TestOps Platform")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
FRONTEND_DIST_DIR = Path(os.getenv("FRONTEND_DIST_DIR", str(BASE_DIR.parent / "frontend" / "public")))