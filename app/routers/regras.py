# app/routers/regras.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from .. import models, services, dependencies
from cachetools import cached

router = APIRouter(
    prefix="/api/regras-negocio",
    tags=["Regras de Negócio"]
)

@router.get("")
@cached(services.cache)
async def get_regras_negocio(user: dict = Depends(dependencies.get_current_user)):
    """Recupera todas as regras de negócio."""
    try:
        queries = {
            "REGRAS_TARIFA_FIXA_ML": f"SELECT * FROM `{services.TABLE_REGRAS_TARIFA_FIXA}` ORDER BY min_venda",
            "CATEGORIAS_PRECIFICACAO": f"SELECT * FROM `{services.TABLE_CATEGORIAS_PRECIFICACAO}` ORDER BY nome",
            "REGRAS_FRETE_ML": f"SELECT * FROM `{services.TABLE_REGRAS_FRETE}` ORDER BY min_venda, min_peso_g"
        }
        results = {key: [dict(row) for row in services.client.query(query)] for key, query in queries.items()}
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras: {e}")

@router.post("/tarifa-fixa")
async def update_regras_tarifa_fixa(payload: List[models.RegraTarifaFixa], user: dict = Depends(dependencies.get_current_admin_user)):
    """Atualiza as regras de tarifa fixa (Apenas Admin)."""
    try:
        services.process_rules(services.TABLE_REGRAS_TARIFA_FIXA, payload, ['id'])
        services.log_action(user['email'], "UPDATE_BUSINESS_RULES", {"rule_type": "TARIFA_FIXA"})
        return {"message": "Regras de tarifa fixa atualizadas."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/categorias")
async def update_regras_categorias(payload: List[models.CategoriaPrecificacao], user: dict = Depends(dependencies.get_current_admin_user)):
    """Atualiza as categorias de precificação (Apenas Admin)."""
    try:
        services.process_rules(services.TABLE_CATEGORIAS_PRECIFICACAO, payload, ['id'])
        services.log_action(user['email'], "UPDATE_BUSINESS_RULES", {"rule_type": "CATEGORIAS"})
        return {"message": "Categorias de precificação atualizadas."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/frete")
async def update_regras_frete(payload: List[models.RegraFrete], user: dict = Depends(dependencies.get_current_admin_user)):
    """Atualiza as regras de frete (Apenas Admin)."""
    try:
        services.process_rules(services.TABLE_REGRAS_FRETE, payload, ['id'])
        services.log_action(user['email'], "UPDATE_BUSINESS_RULES", {"rule_type": "FRETE"})
        return {"message": "Regras de frete atualizadas."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
