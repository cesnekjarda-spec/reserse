from fastapi import Request
from app.config import settings


def template_context(request: Request, **kwargs):
    context = {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        "current_role": getattr(request.state, "current_role", None),
        "settings": settings,
        "flash_success": getattr(request.state, "flash_success", None),
        "flash_error": getattr(request.state, "flash_error", None),
    }
    context.update(kwargs)
    return context
