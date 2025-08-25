# app/routers/campanhas.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/campanhas",
    tags=["Campanhas"]
)

@router.get("", response_model=List[models.CampanhaML])
async def get_campanhas(user: dict = Depends(dependencies.get_current_admin_user)):
    """Recupera todas as campanhas (Apenas Admin)."""
    return services.get_all_campaigns()

@router.post("", status_code=200)
async def save_campanhas(payload: List[models.CampanhaML], user: dict = Depends(dependencies.get_current_admin_user)):
    """Salva/atualiza todas as campanhas (Apenas Admin)."""
    try:
        # Converte a lista de modelos Pydantic para uma lista de dicionários
        campaigns_list = [c.model_dump() for c in payload]
        services.save_all_campaigns(campaigns_list)
        services.log_action(user['email'], "UPDATE_CAMPAIGNS")
        return {"message": "Campanhas atualizadas com sucesso."}
    except Exception as e:
        services.traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ativas", response_model=List[models.CampanhaML])
async def get_active_campaigns_api(user: dict = Depends(dependencies.get_current_user)):
    """Recupera todas as campanhas ativas."""
    return services.get_active_campaigns()