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
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras: {e}")

@router.get("/tarifa-fixa", response_model=List[models.RegraTarifaFixa])
async def get_regras_tarifa_fixa_apenas(user: dict = Depends(dependencies.get_current_user)):
    """Recupera apenas as regras de tarifa fixa do Mercado Livre."""
    try:
        all_rules = await services.get_all_business_rules()
        return all_rules.get("REGRAS_TARIFA_FIXA_ML", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras de tarifa fixa: {e}")

# --- Endpoint Unificado para Salvar Regras ---
# Esta nova abordagem restaura a eficiência do comando MERGE do seu backup.
@router.post("/salvar-todas", status_code=status.HTTP_200_OK)
async def save_all_business_rules(payload: Dict[str, List[Dict]], user: dict = Depends(dependencies.get_current_admin_user)):
    """
    Salva todas as regras de negócio de uma vez, usando a lógica MERGE para eficiência.
    O payload deve ser um dicionário como:
    {
        "REGRAS_TARIFA_FIXA_ML": [...],
        "CATEGORIAS_PRECIFICACAO": [...],
        "REGRAS_FRETE_ML": [...]
    }
    """
    try:
        # Mapeamento para garantir que os dados corretos vão para a função certa
        rule_map = {
            "REGRAS_TARIFA_FIXA_ML": (services.TABLE_REGRAS_TARIFA_FIXA, models.RegraTarifaFixa),
            "CATEGORIAS_PRECIFICACAO": (services.TABLE_CATEGORIAS_PRECIFICACAO, models.CategoriaPrecificacao),
            "REGRAS_FRETE_ML": (services.TABLE_REGRAS_FRETE, models.RegraFrete)
        }

        for key, rules_data in payload.items():
            if key in rule_map:
                table_id, model = rule_map[key]
                # Valida os dados recebidos com o modelo Pydantic
                validated_rules = [model(**rule) for rule in rules_data]
                services.process_rules_with_merge(table_id, validated_rules, ['id'])

        log_action_details = {"updated_rules": list(payload.keys())}
        services.log_action(user['email'], "UPDATE_ALL_BUSINESS_RULES", log_action_details)
        
        return {"message": "Todas as regras de negócio foram salvas com sucesso."}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Erro ao salvar regras: {str(e)}")
