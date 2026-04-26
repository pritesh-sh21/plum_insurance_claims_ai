from dotenv import load_dotenv
load_dotenv()  # Load .env before anything else
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import claims, upload

app = FastAPI(
    title="Plum Claims Processing API",
    description="AI-powered health insurance claims processor",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router, prefix="/api/v1", tags=["claims"])
app.include_router(upload.router, prefix="/api/v1", tags=["upload"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}