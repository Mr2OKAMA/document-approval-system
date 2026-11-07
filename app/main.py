from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from . import core, db
from .routes import admin, auth, documents, equipment, tasks

app = FastAPI(title="文書管理システム", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=core.secret_key(),
    same_site="lax",
    https_only=__import__("os").environ.get("DOCMGMT_HTTPS", "0") == "1",
    max_age=60 * 60 * 8,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.exception_handler(core.Redirect)
async def _redirect(_: Request, exc: core.Redirect):
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(HTTPException)
async def _http_error(request: Request, exc: HTTPException):
    return HTMLResponse(
        f"<!doctype html><meta charset='utf-8'><title>エラー</title><body style='font-family:sans-serif'>"
        f"<h2>{exc.status_code}</h2><p>{__import__('html').escape(str(exc.detail))}</p><p><a href='/'>トップへ</a></p>",
        status_code=exc.status_code,
    )


db.init_db()
for r in (auth, tasks, documents, equipment, admin):
    app.include_router(r.router)
