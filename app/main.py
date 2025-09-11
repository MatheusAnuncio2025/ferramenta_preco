from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler
from starlette.middleware.sessions import SessionMiddleware
import os
from pathlib import Path

from .routers import (
    admin,
    auth,
    campanhas,
    configuracoes,
    dashboard,
    perfil,
    precificacao,
    regras,
    simulador,
)
from .dependencies import (
    get_current_user,
    get_current_admin_user,
    get_historico_viewer_user,
)

app = FastAPI(
    title="Ferramenta de Precificação",
    description="API para a ferramenta de precificação de produtos.",
    version="1.0.0",
)

# ==== Paths do projeto ====
BASE_DIR = Path(__file__).resolve().parent      # /app/app
PROJECT_ROOT = BASE_DIR.parent                  # /app
STATIC_DIR = PROJECT_ROOT / "static"            # /app/static

# ==== Sessão ====
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=bool(os.environ.get("SESSIONS_HTTPS_ONLY", "")),
)

# ==== Arquivos estáticos ====
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ==== Rotas (APIs) ====
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(campanhas.router)
app.include_router(configuracoes.router)
app.include_router(dashboard.router)
app.include_router(perfil.router)
app.include_router(precificacao.router)
app.include_router(regras.router)
app.include_router(simulador.router)

# ==== Tratamento centralizado de HTTPException ====
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Ocorreu um erro."
    if exc.status_code == 401:
        return RedirectResponse(url=f"/?error={detail}", status_code=303)
    if exc.status_code == 403:
        if request.session.get("user"):
            return HTMLResponse(
                content=f"<h1>Acesso Proibido</h1><p>{detail}</p><a href='/'>Voltar</a>",
                status_code=403,
            )
        return RedirectResponse(url="/pendente", status_code=303)
    if exc.status_code == 409:
        return RedirectResponse(url=f"/?error={detail}", status_code=303)
    return await http_exception_handler(request, exc)

# ==== Páginas (HTML) ====
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_root_or_login():
    return FileResponse(str(STATIC_DIR / "login.html"))

@app.get("/calculadora", response_class=HTMLResponse, include_in_schema=False)
async def serve_calculator_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "calculadora.html"))

@app.get("/lista", response_class=HTMLResponse, include_in_schema=False)
async def serve_lista_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "lista.html"))

@app.get("/editar", response_class=HTMLResponse, include_in_schema=False)
async def serve_edit_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "editar.html"))

@app.get("/configuracoes", response_class=HTMLResponse, include_in_schema=False)
async def serve_config_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "configuracoes.html"))

@app.get("/perfil", response_class=HTMLResponse, include_in_schema=False)
async def serve_perfil_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "perfil.html"))

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_page(user: dict = Depends(get_current_admin_user)):
    return FileResponse(str(STATIC_DIR / "admin.html"))

@app.get("/regras", response_class=HTMLResponse, include_in_schema=False)
async def serve_regras_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "regras.html"))

@app.get("/campanhas", response_class=HTMLResponse, include_in_schema=False)
async def serve_campanhas_page(user: dict = Depends(get_current_admin_user)):
    return FileResponse(str(STATIC_DIR / "campanhas.html"))

@app.get("/alertas", response_class=HTMLResponse, include_in_schema=False)
async def serve_alertas_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "alertas.html"))

@app.get("/pendente", response_class=HTMLResponse, include_in_schema=False)
async def serve_pending_page(request: Request):
    if request.session.get("user", {}).get("authorized"):
        return RedirectResponse(url="/calculadora")
    return FileResponse(str(STATIC_DIR / "pendente.html"))

@app.get("/historico", response_class=HTMLResponse, include_in_schema=False)
async def serve_historico_page(user: dict = Depends(get_historico_viewer_user)):
    return FileResponse(str(STATIC_DIR / "historico.html"))

@app.get("/editar-campanha", response_class=HTMLResponse, include_in_schema=False)
async def serve_edit_campaign_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "editar-campanha.html"))

@app.get("/simulador", response_class=HTMLResponse, include_in_schema=False)
async def serve_simulator_page(user: dict = Depends(get_current_user)):
    return FileResponse(str(STATIC_DIR / "simulador.html"))