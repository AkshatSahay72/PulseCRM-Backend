from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS Middleware
# allow_origins=["*"] is fine for local development. For production, restrict to allowed domain names.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root status/welcome endpoint
@app.get("/")
def read_root():
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME} API",
        "status": "healthy",
        "version": "1.0.0"
    }

# Register the versioned API router under /api/v1 prefix
app.include_router(api_router, prefix=settings.API_V1_STR)
