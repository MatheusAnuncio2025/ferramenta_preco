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
async def create_loja_config_api(payload: models.LojaConfigCreate, user: dict = Depends(dependencies.get_current_admin_user)):
    """
    Cria o registro base de uma loja (marketplace + id_loja).
    Observação: O schema da tabela base é simples; este endpoint apenas garante existência e unicidade.
    """
    # Evita duplicidades (marketplace + id_loja)
    existing = [x for x in services.get_lojas_config()
                if x.get("marketplace") == payload.marketplace and x.get("id_loja") == payload.id_loja]
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loja já cadastrada para esse marketplace.")

    # Se o schema exigir ID explícito, gere um e persista via MERGE simples
    new_id = str(services.uuid.uuid4())
    row = {
        "id": new_id,
        "marketplace": payload.marketplace,
        "id_loja": payload.id_loja,
        "nome_loja": payload.nome_loja or None,
    }
    cols = ", ".join(f"`{k}`" for k in row)
    placeholders = ", ".join(f"@{k}" for k in row)
    merge = f"""
        MERGE `{services.TABLE_LOJAS_CONFIG}` T
        USING (SELECT {placeholders}) S
        ON T.marketplace = S.marketplace AND T.id_loja = S.id_loja
        WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({cols})
    """
    params = [services.bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in row.items()]
    services.execute_query(merge, params)
    services.log_action(user.get('email'), "STORE_CONFIG_CREATED", {"id": new_id, "marketplace": payload.marketplace, "id_loja": payload.id_loja})
    return models.LojaConfig(**row)

@router.delete("/lojas/{loja_id}", status_code=204)
async def delete_loja_config_api(loja_id: str, user: dict = Depends(dependencies.get_current_admin_user)):
    """Remove a loja e seus detalhes."""
    services.delete_loja_and_details(loja_id)
    services.log_action(user.get('email'), "STORE_CONFIG_DELETED", {"loja_id": loja_id})

@router.get("/lojas/{loja_id}/detalhes", response_model=models.LojaConfigDetalhes)
async def get_loja_detalhes_api(loja_id: str, user: dict = Depends(dependencies.get_current_user)):
    """Recupera a configuração detalhada de uma loja específica."""
    details = await services.get_loja_details(loja_id)
    return models.LojaConfigDetalhes(**details) if details else models.LojaConfigDetalhes()

@router.post("/lojas/{loja_id}/detalhes", status_code=200)
async def save_loja_detalhes_api(loja_id: str, detalhes: models.LojaConfigDetalhes, user: dict = Depends(dependencies.get_current_user)):
    """Salva a configuração detalhada de uma loja específica."""
    services.save_loja_details(loja_id, detalhes.model_dump_json())
    services.log_action(user.get('email'), "SAVE_STORE_DETAILS", {"loja_id": loja_id})
    return {"message": "Configurações salvas!"}
