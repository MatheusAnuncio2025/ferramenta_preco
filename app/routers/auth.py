# app/routers/auth.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, List
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .. import dependencies

router = APIRouter(tags=["Auth"])

# =============================================================================
# Config / Constantes
# =============================================================================
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

# Leitura de ENV com defaults seguros
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "") or os.getenv("OAUTH_REDIRECT_URI", "")
DEFAULT_SUCCESS_REDIRECT = os.getenv("LOGIN_SUCCESS_REDIRECT", "/calculadora")

# Domínios permitidos (CSV) para conceder "autorizado" por domínio
ALLOWED_DOMAINS = [d.strip().lower() for d in os.getenv("AUTH_ALLOWED_DOMAINS", "").split(",") if d.strip()]
# Lista de e-mails admin (CSV)
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}


# =============================================================================
# Helpers
# =============================================================================
def _services():
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _is_admin(email: str) -> bool:
    s = _services()
    email_l = (email or "").strip().lower()
    if not email_l:
        return False
    # prioridade: services
    try:
        if s and hasattr(s, "is_admin"):
            ret = s.is_admin(email_l)
            if isinstance(ret, bool):
                return ret
    except Exception:
        pass
    # fallback: ADMIN_EMAILS
    return email_l in ADMIN_EMAILS


def _is_authorized(email: str) -> bool:
    s = _services()
    email_l = (email or "").strip().lower()
    if not email_l:
        return False
    # prioridade: services
    try:
        if s and hasattr(s, "is_user_authorized"):
            ret = s.is_user_authorized(email_l)
            if isinstance(ret, bool):
                return ret
    except Exception:
        pass
    # fallback: domínio permitido
    if ALLOWED_DOMAINS:
        domain = email_l.split("@")[-1]
        if domain in ALLOWED_DOMAINS:
            return True
    # admins sempre autorizados
    if _is_admin(email_l):
        return True
    return False


def _enrich_user(email: str, base_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Usa services.get_user_profile(email) (se existir) para enriquecer name/picture."""
    s = _services()
    enriched = dict(base_profile)
    try:
        if s and hasattr(s, "get_user_profile"):
            prof = s.get_user_profile(email) or {}
            if isinstance(prof, dict):
                enriched["name"] = prof.get("name") or enriched.get("name")
                enriched["picture"] = prof.get("picture") or enriched.get("picture")
                roles = prof.get("roles")
                if isinstance(roles, list):
                    enriched["roles"] = roles
    except Exception:
        pass
    return enriched


def _require_oauth_config():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail="Configuração OAuth incompleta (GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI).",
        )


def _session_user_from_google_info(info: Dict[str, Any]) -> Dict[str, Any]:
    email = info.get("email", "")
    name = info.get("name") or info.get("given_name") or email.split("@")[0]
    picture = info.get("picture")
    profile = {"email": email, "name": name, "picture": picture}

    # enriquecer / decidir flags
    profile = _enrich_user(email, profile)
    profile["is_admin"] = _is_admin(email)
    profile["autorizado"] = _is_authorized(email)
    profile["authorized"] = profile["autorizado"]  # compat
    if "roles" not in profile:
        profile["roles"] = ["admin"] if profile["is_admin"] else ["user"]
    return profile


# =============================================================================
# Modelos de resposta
# =============================================================================
class AuthStatus(BaseModel):
    authenticated: bool = False
    user: Optional[Dict[str, Any]] = None
    ts: int = Field(default_factory=lambda: int(time.time()))


# =============================================================================
# Endpoints usados pelo Front
# =============================================================================
@router.get("/api/auth/status", response_model=AuthStatus)
async def auth_status(request: Request) -> AuthStatus:
    """
    Retorna estado de autenticação + dados do usuário (se autenticado).
    Compatível com app.js (isAuthorized/autorizado).
    """
    user = request.session.get("user")
    if not user:
        return AuthStatus(authenticated=False, user=None)
    # garante as chaves padronizadas
    user["autorizado"] = bool(user.get("autorizado") or user.get("authorized") or False)
    user["authorized"] = user["autorizado"]
    user["is_admin"] = bool(user.get("is_admin", False))
    if "roles" not in user:
        user["roles"] = ["admin"] if user["is_admin"] else ["user"]
    return AuthStatus(authenticated=True, user=user)


@router.post("/api/auth/logout")
async def auth_logout(request: Request):
    """
    Faz logout destruindo a sessão atual.
    """
    request.session.clear()
    # Front trata qualquer saída 200 como sucesso
    return {"ok": True}


# =============================================================================
# Fluxo OAuth (Google)
# =============================================================================
@router.get("/login")
async def login(request: Request, action: Optional[str] = None):
    """
    Inicia o fluxo OAuth se action=login; caso contrário, entrega a página / (login.html é servido pelo Main).
    """
    if action != "login":
        # Deixe o main servir a página raiz.
        return RedirectResponse(url="/")

    _require_oauth_config()

    # CSRF 'state'
    state = os.urandom(12).hex()
    request.session["oauth_state"] = state
    request.session["post_login_redirect"] = request.query_params.get("next") or DEFAULT_SUCCESS_REDIRECT

    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/auth")
async def oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None):
    """
    Endpoint de callback do Google OAuth (REDIRECT_URI deve apontar para /auth).
    Salva usuário na sessão e redireciona para a página pós-login.
    """
    _require_oauth_config()

    expected_state = request.session.get("oauth_state")
    if not state or not expected_state or state != expected_state:
        # state inválido → previne CSRF
        raise HTTPException(status_code=400, detail="Estado OAuth inválido.")

    if not code:
        raise HTTPException(status_code=400, detail="Código OAuth ausente.")

    # Troca 'code' por tokens
    token_data: Dict[str, Any]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_res = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_res.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Falha ao obter token: {token_res.text}")
            token_data = token_res.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro de rede/token: {e}")

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Token inválido recebido.")

    # Busca userinfo
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            ui_res = await client.get(
                GOOGLE_USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ui_res.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Falha ao buscar perfil: {ui_res.text}")
            info = ui_res.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro de rede/userinfo: {e}")

    if not info.get("email_verified", True):
        raise HTTPException(status_code=403, detail="E-mail Google não verificado.")

    # Monta o usuário da sessão
    session_user = _session_user_from_google_info(info)
    request.session["user"] = session_user
    # limpeza de estado
    request.session.pop("oauth_state", None)

    # Redireciona para a página pós-login
    next_url = request.session.pop("post_login_redirect", DEFAULT_SUCCESS_REDIRECT)
    return RedirectResponse(url=next_url, status_code=303)
