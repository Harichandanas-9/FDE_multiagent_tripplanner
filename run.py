"""Entry point. Run with: python run.py"""

import os
import sys
from pathlib import Path
import uvicorn

# Add project root to Python path
ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import FastAPI app
from server import app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )