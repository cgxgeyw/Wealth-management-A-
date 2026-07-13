import os
import tempfile
from pathlib import Path


_TEST_ROOT = Path(tempfile.mkdtemp(prefix="ashare-agent-tests-")).resolve()

# This must run before test modules import app.settings or app.db.session.
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT / 'app.db'}"
os.environ["FAISS_INDEX_DIR"] = str(_TEST_ROOT / "faiss")
