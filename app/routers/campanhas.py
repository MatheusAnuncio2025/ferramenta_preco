# app/routers/campanhas.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from .. import models, services, dependencies
from cachetools import cached

router = APIRouter(
    prefix="/api/campanhas",
    tags=["Campanhas"]
)

@router.get("", response_model=List[models.CampanhaML])
@cached(services.cache)
async def get_campanhas(user: dict = Depends(dependencies.get_current_admin_user)):
    """Recupera todas as campanhas (Apenas Admin)."""
    query = f"SELECT * FROM `{services.TABLE_CAMPANHAS_ML}` ORDER BY data_fim DESC, nome"
    results = services.client.query(query).result()
    return [dict(row) for row in results]

@router.post("", status_code=200)
async def save_campanhas(payload: List[models.CampanhaML], user: dict = Depends(dependencies.get_current_admin_user)):
    """Salva/atualiza todas as campanhas (Apenas Admin)."""
    try:
        services.process_rules(services.TABLE_CAMPANHAS_ML, payload, ['id'])
        services.log_action(user['email'], "UPDATE_CAMPAIGNS")
        return {"message": "Campanhas atualizadas com sucesso."}
    except Exception as e:
        services.traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ativas", response_model=List[models.CampanhaML])
@cached(services.cache)
async def get_active_campaigns(user: dict = Depends(dependencies.get_current_user)):
    """Recupera todas as campanhas ativas."""
    query = f"SELECT * FROM `{services.TABLE_CAMPANHAS_ML}` WHERE data_fim >= CURRENT_DATE() OR data_fim IS NULL ORDER BY nome"
    results = services.client.query(query).result()
    return [models.CampanhaML(**row) for row in results]
