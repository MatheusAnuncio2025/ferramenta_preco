# app/routers/configuracoes.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from .. import dependencies

router = APIRouter(prefix="/api/config", tags=["Configurações"])

# =============================================================================
# Modelos (Pydantic)
# =============================================================================
class LojaItem(BaseModel):
    id: str = Field(..., description="ID interno da loja (UUID ou similar)")
    marketplace: str = Field(..., description="Nome do marketplace (ex.: Mercado Livre)")
    id_loja: str = Field(..., description="Identificador da loja no marketplace (ex.: 'Julishop')")
    nome: str = Field(..., description="Nome amigável (compatibilidade com UI)")
    data_criacao: Optional[str] = Field(None, description="ISO datetime da criação (opcional)")


class ComissaoRegra(BaseModel):
    chave: str = Field(..., description="Identificador da regra (ex.: 'padrão_ML')")
    classico: float = 0.0
    premium: float = 0.0


class LojaDetalhes(BaseModel):
    id: Optional[str] = None
    marketplace: Optional[str] = None
    id_loja: Optional[str] = None
    aliquota_padrao: float = 0.0
    aliquota_fulfillment: float = 0.0
    comissoes: List[ComissaoRegra] = Field(default_factory=list)


# =============================================================================
# Helpers seguros (integração com services + fallbacks)
# =============================================================================
def _try_import_services():
    try:
        from app import services  # type: ignore
        return services
    except Exception:
        return None


def _safe_list_lojas() -> List[Dict[str, Any]]:
    """
    Busca lista de lojas via services.get_stores(), se existir.
    Normaliza as chaves esperadas pelo front + validação pydantic.
    """
    services = _try_import_services()
    raw_rows: List[Dict[str, Any]] = []
    if services and hasattr(services, "get_stores"):
        try:
            rows = services.get_stores() or []
            if isinstance(rows, list):
                raw_rows = rows
        except Exception:
            raw_rows = []

    # Se não houver fonte, devolve lista vazia (nunca 500)
    out: List[Dict[str, Any]] = []
    for r in raw_rows:
        if not isinstance(r, dict):
            continue
        id_ = str(r.get("id") or r.get("uuid") or r.get("store_id") or "")
        marketplace = str(r.get("marketplace") or r.get("canal") or "")
        id_loja = str(r.get("id_loja") or r.get("loja") or r.get("nome_loja") or "")
        data_criacao = r.get("data_criacao")
        # Compat: `nome` exigido pelo modelo → usar id_loja se não houver outro
        nome = str(r.get("nome") or id_loja or "").strip() or f"{marketplace} - {id_loja}"

        if not id_:
            # ignora linhas sem ID
            continue

        out.append(
            {
                "id": id_,
                "marketplace": marketplace,
                "id_loja": id_loja,
                "nome": nome,
                "data_criacao": data_criacao if isinstance(data_criacao, str) else None,
            }
        )

    return out


def _safe_loja_detalhes(store_id: str) -> LojaDetalhes:
    """
    Busca detalhes de loja via services.get_store_details(id), se existir.
    Fallback seguro para defaults.
    """
    services = _try_import_services()
    detalhe: Dict[str, Any] = {}
    if services and hasattr(services, "get_store_details"):
        try:
            raw = services.get_store_details(store_id) or {}
            if isinstance(raw, dict):
                detalhe = raw
        except Exception:
            detalhe = {}

    # Normalização/compatibilidade
    aliquota_padrao = float(detalhe.get("aliquota_padrao") or detalhe.get("aliquota") or 0.0)
    aliquota_fulfillment = float(detalhe.get("aliquota_fulfillment") or detalhe.get("aliquota_ff") or 0.0)

    comissoes_raw = detalhe.get("comissoes") or []
    comissoes: List[Dict[str, Any]] = []
    if isinstance(comissoes_raw, list):
        for c in comissoes_raw:
            if not isinstance(c, dict):
                continue
            comissoes.append(
                {
                    "chave": str(c.get("chave") or c.get("nome") or "padrao"),
                    "classico": float(c.get("classico") or c.get("taxa_classico") or 0.0),
                    "premium": float(c.get("premium") or c.get("taxa_premium") or 0.0),
                }
            )

    # Alguns metadados úteis
    id_loja = detalhe.get("id_loja")
    marketplace = detalhe.get("marketplace")

    # Monta o objeto final (validado por Pydantic)
    return LojaDetalhes(
        id=store_id,
        marketplace=marketplace,
        id_loja=id_loja,
        aliquota_padrao=aliquota_padrao,
        aliquota_fulfillment=aliquota_fulfillment,
        comissoes=[ComissaoRegra(**c) for c in comissoes],
    )


# =============================================================================
# Endpoints
# =============================================================================
@router.get("/lojas", response_model=List[LojaItem], summary="Lista lojas configuradas")
async def list_lojas(user: dict = Depends(dependencies.get_current_user)) -> List[LojaItem]:
    """
    Lista de lojas. Inclui a chave `nome` (compatibilidade com validação/UI).
    """
    try:
      lojas = _safe_list_lojas()
      # Validação Pydantic aqui garante formato consistente
      return [LojaItem(**x) for x in lojas]
    except Exception as e:
      # Nunca quebrar com 500 por formato inesperado
      raise HTTPException(status_code=400, detail=f"Falha ao listar lojas: {e}")


@router.get("/lojas/{store_id}/detalhes", response_model=LojaDetalhes, summary="Detalhes de uma loja")
async def loja_detalhes(store_id: str, user: dict = Depends(dependencies.get_current_user)) -> LojaDetalhes:
    """
    Detalhes de loja (comissões e alíquotas). Estrutura compatível com o front.
    """
    try:
        return _safe_loja_detalhes(store_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao obter detalhes da loja: {e}")
