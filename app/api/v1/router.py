"""
Роуты API v1
"""

from fastapi import APIRouter

from app.api.v1.endpoints import payment, callback

api_v1_router = APIRouter()

# Подключение роутов
api_v1_router.include_router(
    payment.router,
    prefix="",
    tags=["payments"]
)

api_v1_router.include_router(
    callback.router,
    prefix="/callback",
    tags=["callbacks"]
)

@api_v1_router.get("/info")
async def api_v1_info() -> dict[str, str]:
    """
    Информация об API v1
    
    Returns:
        dict: Информация о версии API
    """
    return {
        "version": "1.0",
        "status": "active",
        "description": "СБП API версия 1.0"
    }