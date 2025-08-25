# app/main.py
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler
from starlette.middleware.sessions import SessionMiddleware
import os
from .routers import admin, auth, campanhas, configuracoes, dashboard, perfil, precificacao, regras
from .dependencies import get_current_user, get_current_admin_user, get_historico_viewer_user

app = FastAPI(
    title="Ferramenta de Precificação",
    description="API para a ferramenta de precificação de produtos.",
    version="1.0.0"
)

# --- Middlewares e Configurações ---
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "uma_chave_secreta_padrao_para_desenvolvimento_local"))

# --- Montar Arquivos Estáticos ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Incluir Roteadores da API ---
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(campanhas.router)
app.include_router(configuracoes.router)
app.include_router(dashboard.router)
app.include_router(perfil.router)
app.include_router(precificacao.router)
app.include_router(regras.router)

# --- Tratamento de Exceções Global ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Ocorreu um erro."
    if exc.status_code == 401:
        return RedirectResponse(url=f"/?error={detail}", status_code=303)
    if exc.status_code == 403:
        if request.session.get('user'):
             return HTMLResponse(content=f"<h1>Acesso Proibido</h1><p>{detail}</p><a href='/'>Voltar</a>", status_code=403)
        return RedirectResponse(url="/pendente", status_code=303)
    if exc.status_code == 409:
         return RedirectResponse(url=f"/?error={detail}", status_code=303)
    return await http_exception_handler(request, exc)

# --- Rotas para Servir Páginas HTML ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_root_or_login(): return FileResponse('static/login.html')

@app.get("/calculadora", response_class=HTMLResponse, include_in_schema=False)
async def serve_calculator_page(user: dict = Depends(get_current_user)): return FileResponse('static/calculadora.html')

@app.get("/lista", response_class=HTMLResponse, include_in_schema=False)
async def serve_lista_page(user: dict = Depends(get_current_user)): return FileResponse('static/lista.html')

@app.get("/editar", response_class=HTMLResponse, include_in_schema=False)
async def serve_edit_page(user: dict = Depends(get_current_user)): return FileResponse('static/editar.html')

@app.get("/configuracoes", response_class=HTMLResponse, include_in_schema=False)
async def serve_config_page(user: dict = Depends(get_current_user)): return FileResponse('static/configuracoes.html')

@app.get("/perfil", response_class=HTMLResponse, include_in_schema=False)
async def serve_perfil_page(user: dict = Depends(get_current_user)): return FileResponse('static/perfil.html')

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_page(user: dict = Depends(get_current_admin_user)): return FileResponse('static/admin.html')

@app.get("/regras", response_class=HTMLResponse, include_in_schema=False)
async def serve_regras_page(user: dict = Depends(get_current_user)): return FileResponse('static/regras.html')

@app.get("/campanhas", response_class=HTMLResponse, include_in_schema=False)
async def serve_campanhas_page(user: dict = Depends(get_current_admin_user)): return FileResponse('static/campanhas.html')

@app.get("/alertas", response_class=HTMLResponse, include_in_schema=False)
async def serve_alertas_page(user: dict = Depends(get_current_user)): return FileResponse('static/alertas.html')

@app.get("/pendente", response_class=HTMLResponse, include_in_schema=False)
async def serve_pending_page(request: Request):
    if request.session.get("user", {}).get("authorized"): return RedirectResponse(url="/calculadora")
    return FileResponse('static/pendente.html')

@app.get("/historico", response_class=HTMLResponse, include_in_schema=False)
async def serve_historico_page(user: dict = Depends(get_historico_viewer_user)): return FileResponse('static/historico.html')

@app.get("/editar-campanha", response_class=HTMLResponse, include_in_schema=False)
async def serve_edit_campaign_page(user: dict = Depends(get_current_user)): return FileResponse('static/editar-campanha.html')
