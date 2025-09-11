# app/routers/admin.py
from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import dependencies

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# =============================================================================
# Helpers (services + fallbacks)
# =============================================================================
def _services():
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _safe(fn_name: str, *args, **kwargs):
    s = _services()
    if not s:
        return None
    fn = getattr(s, fn_name, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _norm_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "t", "yes", "y", "sim"}
    return default


def _norm_user(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza para o shape esperado pela UI de Admin."""
    email = str(row.get("email") or row.get("username") or "").lower()
    name = row.get("name") or row.get("display_name") or email.split("@")[0] if email else ""
    picture = row.get("picture") or row.get("avatar") or None
    autorizado = _norm_bool(row.get("autorizado") or row.get("authorized") or row.get("is_authorized"), False)
    is_admin = _norm_bool(row.get("is_admin") or row.get("admin"), False)
    roles = row.get("roles")
    if not isinstance(roles, list):
        roles = ["admin"] if is_admin else ["user"]
    last_login = row.get("last_login") or row.get("last_seen") or None

    return {
        "email": email,
        "name": name,
        "picture": picture,
        "autorizado": autorizado,
        "authorized": autorizado,  # compat
        "is_admin": is_admin,
        "roles": roles,
        "last_login": last_login,
    }


# =============================================================================
# Models (request/response)
# =============================================================================
class AdminUserItem(BaseModel):
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    autorizado: bool = False
    authorized: bool = False
    is_admin: bool = False
    roles: List[str] = Field(default_factory=lambda: ["user"])
    last_login: Optional[str] = None


class AdminUsersResponse(BaseModel):
    users: List[AdminUserItem] = Field(default_factory=list)


class AuthorizeUserPayload(BaseModel):
    email: str
    autorizado: bool


class SetRolePayload(BaseModel):
    email: str
    is_admin: bool


class LogEntry(BaseModel):
    ts: Optional[str] = None
    level: Optional[str] = None
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class LogsResponse(BaseModel):
    items: List[LogEntry] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    python: str = Field(default_factory=lambda: sys.version.split()[0])
    platform: str = Field(default_factory=platform.platform)
    app_version: Optional[str] = os.getenv("APP_VERSION")
    env: Optional[str] = os.getenv("APP_ENV")


# =============================================================================
# Endpoints (somente ADMIN)
# =============================================================================
@router.get("/usuarios", response_model=AdminUsersResponse, summary="Lista de usuários")
async def list_users(user: dict = Depends(dependencies.get_current_admin_user)) -> AdminUsersResponse:
    """
    Lista usuários. Integra com:
      - services.list_users()   -> [ { email, name, authorized/autorizado, is_admin, roles, picture, last_login } ]
      - services.get_all_users() (fallback)
    Nunca retorna 500; devolve lista vazia no pior caso.
    """
    rows = []
    for fn in ("list_users", "get_all_users"):
        res = _safe(fn)
        if isinstance(res, list):
            rows = res
            break

    users = []
    for r in rows or []:
        if isinstance(r, dict):
            users.append(AdminUserItem(**_norm_user(r)))
    return AdminUsersResponse(users=users)


@router.post("/usuarios/authorize", summary="Autoriza/Desautoriza usuário")
async def authorize_user(payload: AuthorizeUserPayload, user: dict = Depends(dependencies.get_current_admin_user)):
    """
    Define flag de autorização de um usuário.
    Integra com services.set_user_authorized(email, autorizado: bool)
    """
    email = (payload.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="E-mail inválido.")

    ok = _safe("set_user_authorized", email, bool(payload.autorizado))
    if ok is False:
        raise HTTPException(status_code=400, detail="Falha ao atualizar autorização do usuário.")
    return {"ok": True}


@router.post("/usuarios/role", summary="Promove/Rebaixa admin")
async def set_user_role(payload: SetRolePayload, user: dict = Depends(dependencies.get_current_admin_user)):
    """
    Promove/Rebaixa privilégios de admin.
    Integra com services.set_admin(email, is_admin: bool)
    """
    email = (payload.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="E-mail inválido.")

    ok = _safe("set_admin", email, bool(payload.is_admin))
    if ok is False:
        raise HTTPException(status_code=400, detail="Falha ao atualizar papel do usuário.")
    return {"ok": True}


@router.get("/logs", response_model=LogsResponse, summary="Últimos logs")
async def get_logs(limit: int = 200, user: dict = Depends(dependencies.get_current_admin_user)) -> LogsResponse:
    """
    Retorna últimos logs (se o backend expuser). Fallback para vazio.
    Integra com services.get_recent_logs(limit) -> [ { ts, level, message, meta } ]
    """
    rows = _safe("get_recent_logs", int(limit)) or []
    items: List[LogEntry] = []
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict):
                items.append(
                    LogEntry(
                        ts=r.get("ts") or r.get("timestamp"),
                        level=r.get("level") or r.get("lvl"),
                        message=r.get("message") or r.get("msg"),
                        meta=r.get("meta") if isinstance(r.get("meta"), dict) else None,
                    )
                )
    return LogsResponse(items=items)


@router.get("/health", response_model=HealthResponse, summary="Healthcheck")
async def health(user: dict = Depends(dependencies.get_current_admin_user)) -> HealthResponse:
    """
    Health simples da aplicação (somente admin na API para evitar exposição).
    """
    return HealthResponse()
