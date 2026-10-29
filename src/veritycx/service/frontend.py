"""Serve the built customer page and bounded public assets from the existing local API."""

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from veritycx import PROJECT_ROOT

FRONTEND_ROOT = PROJECT_ROOT / "dist" / "chat"


def register_frontend(app: FastAPI, directory: Path, widget_origin: str | None = None) -> None:
    """Serve public build artifacts only; never mount project files or inject credentials."""
    assets = directory / "assets"
    if assets.is_dir():
        app.mount(
            "/assets", StaticFiles(directory=assets, follow_symlink=False), name="chat-assets"
        )
    allowed = f" {widget_origin}" if widget_origin else ""
    policy = (
        "default-src 'self'; "
        f"script-src 'self'{allowed}; "
        "style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data:{allowed}; "
        f"connect-src 'self'{allowed}; "
        f"frame-src 'self'{allowed}; "
        "font-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    )

    @app.get("/", include_in_schema=False)
    @app.get("/chat", include_in_schema=False)
    async def customer_page() -> Response:
        """Return the built page or an explicit unavailable response without private paths."""
        index = directory / "index.html"
        if not index.is_file() or index.is_symlink():
            return JSONResponse({"status": "frontend_unavailable"}, status_code=503)
        return FileResponse(
            index,
            media_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": policy,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "same-origin",
            },
        )
