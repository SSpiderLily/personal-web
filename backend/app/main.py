from secrets import randbelow

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.settings import get_settings
from app.admin_routes import router as admin_router
from app.tool_routes import router as tool_router
from app.admin_uploads import router as upload_router
from app.statistics_routes import router as statistics_router
from app.project_routes import router as project_router
from app.profile_routes import router as profile_router
from app.public_file_routes import router as public_file_router

settings = get_settings()
app = FastAPI(title="Personal Website API", version="0.1.0", debug=settings.debug)
app.include_router(admin_router)
app.include_router(tool_router)
app.include_router(upload_router)
app.include_router(statistics_router)
app.include_router(project_router)
app.include_router(profile_router)
app.include_router(public_file_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}


class DiceResult(BaseModel):
    value: int = Field(ge=1, le=6)


@app.post("/api/dice/roll", response_model=DiceResult)
def roll_dice():
    return DiceResult(value=randbelow(6) + 1)
