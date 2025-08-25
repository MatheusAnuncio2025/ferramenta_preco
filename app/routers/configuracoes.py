# app/routers/configuracoes.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/config",
    tags=["Configurações"]
)

@router.get("/lojas", response_model=List[models.LojaConfig])
async def get_lojas_config_api(user: dict = Depends(dependencies.get_current_user)):
    """Recupera a lista de lojas configuradas."""
    return services.get_lojas_config()

@router.post("/lojas", response_model=models.LojaConfig, status_code=201)
async def add_loja(loja_data: models.NewLojaConfig, user: dict = Depends(dependencies.get_current_user)):
    """Adiciona uma nova configuração de loja."""
    try:
        id = str(services.uuid.uuid4())
        row_to_insert = [{"id": id, "marketplace": loja_data.marketplace, "id_loja": loja_data.id_loja}]
        errors = services.client.insert_rows_json(services.TABLE_LOJAS_CONFIG, row_to_insert)
        if errors:
            raise HTTPException(status_code=500, detail=f"Erro ao adicionar loja: {errors}")
        
        services.log_action(user.get('email'), "STORE_CONFIG_ADDED", {"loja_id": id})
        return models.LojaConfig(id=id, **loja_data.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar loja: {e}")


@router.delete("/lojas/{loja_id}", status_code=204)
async def delete_loja(loja_id: str, user: dict = Depends(dependencies.get_current_user)):
    """Deleta uma loja e seus detalhes."""
    services.delete_loja_and_details(loja_id)
    services.log_action(user.get('email'), "STORE_CONFIG_DELETED", {"loja_id": loja_id})

@router.get("/lojas/{loja_id}/detalhes", response_model=models.LojaConfigDetalhes)
async def get_loja_detalhes_api(loja_id: str, user: dict = Depends(dependencies.get_current_user)):
    """Recupera a configuração detalhada de uma loja específica."""
    details = services.get_loja_details(loja_id)
    return models.LojaConfigDetalhes(**details) if details else models.LojaConfigDetalhes()
    
@router.post("/lojas/{loja_id}/detalhes", status_code=200)
async def save_loja_detalhes_api(loja_id: str, detalhes: models.LojaConfigDetalhes, user: dict = Depends(dependencies.get_current_user)):
    """Salva a configuração detalhada de uma loja específica."""
    services.save_loja_details(loja_id, detalhes.model_dump_json())
    services.log_action(user.get('email'), "SAVE_STORE_DETAILS", {"loja_id": loja_id})
    return {"message": "Configurações salvas!"}