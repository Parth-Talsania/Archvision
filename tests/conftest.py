import os
import tempfile
from pathlib import Path

# Point the backend at a throwaway SQLite database *before* anything imports
# backend.config, so tests never touch backend/archvision.db.
_TEST_DIR = Path(tempfile.mkdtemp(prefix="archvision-tests-"))
os.environ["ARCHVISION_DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / 'test.db').as_posix()}"
os.environ.setdefault("ARCHVISION_SECRET_KEY", "test-secret-key")
