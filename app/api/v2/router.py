"""
Роуты API v2
"""

from fastapi import APIRouter

api_v2_router = APIRouter()

@api_v2_router.get("/info")
async def api_v2_info() -> dict[str, str]:
    """
    Информация об API v2
    
    Returns:
        dict: Информация о версии API
    """
    return {
        "version": "2.0",
        "status": "coming_soon",
        "description": "СБП API версия 2.0 (в разработке)"
    }