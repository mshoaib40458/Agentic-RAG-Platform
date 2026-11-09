import os
import sys

os.environ["GRADIO_SSR_MODE"] = "false"
os.environ["SETTINGS_IGNORE_DOTENV"] = "1"

import subprocess
from pathlib import Path
import gradio as gr

# Ensure backend directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Tell settings to ignore local .env so production secrets always win
os.environ["SETTINGS_IGNORE_DOTENV"] = "1"

# Change current working directory to backend so relative data paths work seamlessly
os.chdir(str(BACKEND_DIR))

# Ensure required storage folders exist
os.makedirs(BACKEND_DIR / "data" / "storage" / "qdrant", exist_ok=True)
os.makedirs(BACKEND_DIR / "data" / "storage" / "uploads", exist_ok=True)

# Run database migrations
try:
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print("Database migrations applied successfully.")
except Exception as e:
    print(f"Notice during database migration: {e}")

# Import the FastAPI application
from app.main import create_app

fastapi_app = create_app()

# Gradio Interface for Hugging Face preview
with gr.Blocks(title="Agentic RAG Platform API") as demo:
    gr.Markdown("# 🚀 Agentic RAG Platform — Backend API")
    gr.Markdown(
        """
        The Agentic RAG Platform backend service is **online and active**!
        
        ### Quick Links:
        * 📖 **Interactive API Documentation:** [/docs](/docs)
        * 🏥 **System Health Check:** [/api/v1/health](/api/v1/health)
        * 💻 **Client Application:** Connects with the React frontend hosted on Vercel.
        """
    )

# Mount Gradio onto the FastAPI application
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)

