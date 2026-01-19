"""
Root entry point for Railway deployment
This file is in the ROOT directory, not inside app/
"""

import os
from app.main import app  # استورد FastAPI app من app/main.py

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
