"""
Health check endpoint для мониторинга работоспособности сервиса
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    Эндпоинт для проверки работоспособности сервиса.
    Не требует аутентификации, используется Docker healthcheck и системами мониторинга.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "ok"}
    )

