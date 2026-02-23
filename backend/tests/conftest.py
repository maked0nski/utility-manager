import sys
from pathlib import Path


# Ensure backend project root is importable in containerized pytest runs.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
