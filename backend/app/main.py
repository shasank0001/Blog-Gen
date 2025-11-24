from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import ingestion, agent, auth, bins, profiles, threads
from app.core.database import init_db
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.PROJECT_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    # await init_db()
    pass

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(bins.router, prefix="/api/v1/bins", tags=["bins"])
app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["profiles"])
app.include_router(threads.router, prefix="/api/v1/threads", tags=["threads"])
app.include_router(ingestion.router, prefix="/api/v1", tags=["ingestion"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])

@app.get("/")
def read_root():
    return {"message": "Content Strategist Agent API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
