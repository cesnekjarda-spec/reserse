from fastapi import Request


def template_context(request: Request, **kwargs):
    context = {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        "flash_success": getattr(request.state, "flash_success", None),
        "flash_error": getattr(request.state, "flash_error", None),
    }
    context.update(kwargs)
    return context
