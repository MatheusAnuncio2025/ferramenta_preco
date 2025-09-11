# app/routers/campanhas.py
from __future__ import annotations

from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from .. import models, services, dependencies


router = APIRouter(
    prefix="/api/campanhas",
    tags=["Campanhas"],
)


def _coerce_campaign_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza chaves esperadas pela UI, mantendo extras do BigQuery.
    Garante presença (com None) das chaves usadas no front:
      id, nome, tipo_campanha, tipo_cupom, valor_cupom, tipo_cashback,
      valor_cashback, data_inicio, data_fim
    """
    expected_keys = [
        "id",
        "nome",
        "tipo_campanha",
        "tipo_cupom",
        "valor_cupom",
        "tipo_cashback",
        "valor_cashback",
        "data_inicio",
        "data_fim",
    ]
    out = dict(row) if isinstance(row, dict) else {}
    for k in expected_keys:
        out.setdefault(k, None)
    return out


@router.get("", summary="Lista todas as campanhas (admin)")
async def get_campanhas(
    user: dict = Depends(dependencies.get_current_admin_user),
) -> List[Dict[str, Any]]:
    """Recupera todas as campanhas (somente Admin).
    Retorna lista de dicionários, normalizada para evitar erros de validação.
    """
    try:
        rows = services.get_all_campaigns() or []
        return [_coerce_campaign_row(r) for r in rows]
    except Exception as e:
        services.logger.error(f"Erro ao listar campanhas: {e}", exc_info=True)
        # Evita 500, informa causa ao cliente
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", summary="Salva/atualiza campanhas (admin)", status_code=200)
async def save_campanhas(
    payload: List[models.CampanhaML],
    user: dict = Depends(dependencies.get_current_admin_user),
):
    """Salva/atualiza todas as campanhas. Substitui o conjunto atual pelo enviado."""
    try:
        campaigns_list = [c.model_dump() for c in payload]
        services.save_all_campaigns(campaigns_list)
        services.log_action(user.get("email", "unknown@local"), "UPDATE_CAMPAIGNS")
        return {"message": "Campanhas atualizadas com sucesso."}
    except Exception as e:
        services.logger.error(f"Erro ao salvar campanhas: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ativas", summary="Campanhas ativas", response_model=List[Dict[str, Any]])
async def get_active_campaigns_api(user: dict = Depends(dependencies.get_current_user)):
    """Recupera campanhas ativas para uso geral (não requer admin)."""
    try:
        rows = services.get_active_campaigns() or []
        return [_coerce_campaign_row(r) for r in rows]
    except Exception as e:
        services.logger.error(f"Erro ao listar campanhas ativas: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
