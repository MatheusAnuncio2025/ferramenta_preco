# app/routers/regras.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict
from .. import models, services, dependencies
import traceback

router = APIRouter(
    prefix="/api/regras-negocio",
    tags=["Regras de Negócio"]
)

@router.get("", response_model=models.AllBusinessRules)
async def get_regras_negocio(user: dict = Depends(dependencies.get_current_user)):
    """Recupera todas as regras de negócio."""
    try:
        return await services.get_all_business_rules()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras de negócio: {e}")

# Listagens diretas (úteis para telas dedicadas)
@router.get("/tarifa-fixa", response_model=List[models.RegraTarifaFixa])
async def get_tarifa_fixa(user: dict = Depends(dependencies.get_current_user)):
    try:
        all_rules = await services.get_all_business_rules()
        return [models.RegraTarifaFixa(**r) for r in all_rules.get("REGRAS_TARIFA_FIXA_ML", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras de tarifa fixa: {e}")

@router.get("/frete", response_model=List[models.RegraFrete])
async def get_regra_frete(user: dict = Depends(dependencies.get_current_user)):
    try:
        all_rules = await services.get_all_business_rules()
        return [models.RegraFrete(**r) for r in all_rules.get("REGRAS_FRETE_ML", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras de frete: {e}")

@router.get("/categorias", response_model=List[models.CategoriaPrecificacao])
async def get_categorias_precificacao(user: dict = Depends(dependencies.get_current_user)):
    try:
        all_rules = await services.get_all_business_rules()
        return [models.CategoriaPrecificacao(**r) for r in all_rules.get("CATEGORIAS_PRECIFICACAO", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar categorias: {e}")

# Unificado para salvar todas as regras (usa MERGE no services)
@router.post("/salvar-todas", status_code=status.HTTP_200_OK)
async def save_all_business_rules(payload: Dict[str, List[Dict]], user: dict = Depends(dependencies.get_current_admin_user)):
    """
    Salva todas as regras de uma vez. Espera um payload:
    {
        "REGRAS_TARIFA_FIXA_ML": [...],
        "CATEGORIAS_PRECIFICACAO": [...],
        "REGRAS_FRETE_ML": [...]
    }
    """
    try:
        rule_map = {
            "REGRAS_TARIFA_FIXA_ML": (services.TABLE_REGRAS_TARIFA_FIXA, models.RegraTarifaFixa),
            "CATEGORIAS_PRECIFICACAO": (services.TABLE_CATEGORIAS_PRECIFICACAO, models.CategoriaPrecificacao),
            "REGRAS_FRETE_ML": (services.TABLE_REGRAS_FRETE, models.RegraFrete),
        }
        for key, rules_data in payload.items():
            if key not in rule_map:
                continue
            table_id, Model = rule_map[key]
            validated = [Model(**rule) for rule in rules_data]
            services.process_rules_with_merge(table_id, validated, ['id'])
        services.log_action(user['email'], "UPDATE_ALL_BUSINESS_RULES", {"updated_rules": list(payload.keys())})
        return {"message": "Regras salvas com sucesso."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Erro ao salvar regras: {str(e)}")
