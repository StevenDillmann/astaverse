"""FastAPI adapter.

Thin by design: routers resolve an analysis, call into `core`, and shape the
result. The CLI adapter calls the same `core` functions, so the two surfaces
cannot diverge in behaviour, and both read their options from the same
`RunConfig` schema.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ...paths import WEB_DIST
from . import analyses, catalog, files

app = FastAPI(title="Astaverse", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(analyses.router)
app.include_router(files.router)


if (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

else:

    @app.get("/")
    def index_missing() -> dict[str, str]:
        return {
            "message": (
                "Web interface not built. Run `npm install && npm run build` in web/, "
                "or `npm run dev` for the dev server on :5173."
            )
        }
