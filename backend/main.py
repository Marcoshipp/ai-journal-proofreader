import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure backend dir is on the Python path so subpackage imports work
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

app = FastAPI(title="Academic Journal Proofreader API")

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
from validate_routes import router as validate_router
from config_routes import router as config_router

app.include_router(validate_router)
app.include_router(config_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
