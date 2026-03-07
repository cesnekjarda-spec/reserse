from fastapi import Request


def template_context(request: Request, **kwargs):
    return {"request": request, "current_user": getattr(request.state, "current_user", None), **kwargs}
