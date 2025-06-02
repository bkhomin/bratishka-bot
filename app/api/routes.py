from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.services.summary_service import SummaryService
from app.core.metrics import app_metrics
from pydantic import BaseModel

app = FastAPI(title="Bratishka Agent API", version="1.0.0")


class SummaryRequest(BaseModel):
    chat_id: str
    hours_back: int = 24


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "metrics": {
            "requests_total": app_metrics.requests_total,
            "error_rate": app_metrics.error_rate,
            "avg_response_time": app_metrics.avg_response_time
        }
    }


@app.post("/api/v1/summary")
async def create_summary(
        request: SummaryRequest,
        db: AsyncSession = Depends(get_db)
):
    summary_service = SummaryService()
    result = await summary_service.create_chat_summary(
        db, request.chat_id, request.hours_back
    )

    if result["status"] != "success":
        raise HTTPException(status_code=400, detail=result["message"])

    return result
