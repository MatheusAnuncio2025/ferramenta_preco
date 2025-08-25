# app/routers/configuracoes.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import models, services, dependencies
from cachetools import cached

router = APIRouter(
    prefix="/api/config",
    tags=["Configurações"]
)

@router.get("/lojas", response_model=List[models.LojaConfig])
@cached(services.cache)
async def get_lojas_config_api(user: dict = Depends(dependencies.get_current_user)):
    """Recupera a lista de lojas configuradas."""
    query = f"SELECT * FROM `{services.TABLE_LOJAS_CONFIG}` ORDER BY marketplace, id_loja"
    return [dict(row) for row in services.client.query(query)]

@router.post("/lojas", response_model=models.LojaConfig, status_code=201)
async def add_loja(loja_data: models.NewLojaConfig, user: dict = Depends(dependencies.get_current_user)):
    """Adiciona uma nova configuração de loja."""
    id = str(services.uuid.uuid4())
    row_to_insert = [{"id": id, "marketplace": loja_data.marketplace, "id_loja": loja_data.id_loja}]
    errors = services.client.insert_rows_json(services.TABLE_LOJAS_CONFIG, row_to_insert)
    if errors:
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar loja: {errors}")
    services.log_action(user.get('email'), "STORE_CONFIG_ADDED", {"loja_id": id})
    return models.LojaConfig(id=id, **loja_data.model_dump())

@router.delete("/lojas/{loja_id}", status_code=204)
async def delete_loja(loja_id: str, user: dict = Depends(dependencies.get_current_user)):
    """Deleta uma loja e seus detalhes."""
    params = [services.bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id)]
    job_config = services.bigquery.QueryJobConfig(query_parameters=params)
    services.client.query(f"DELETE FROM `{services.TABLE_LOJAS_CONFIG}` WHERE id = @loja_id", job_config=job_config).result()
    services.client.query(f"DELETE FROM `{services.TABLE_LOJA_CONFIG_DETALHES}` WHERE loja_id = @loja_id", job_config=job_config).result()
    services.log_action(user.get('email'), "STORE_CONFIG_DELETED", {"loja_id": loja_id})

@router.get("/lojas/{loja_id}/detalhes", response_model=models.LojaConfigDetalhes)
@cached(services.cache)
async def get_loja_detalhes(loja_id: str, user: dict = Depends(dependencies.get_current_user)):
    """Recupera a configuração detalhada de uma loja específica."""
    query = f"SELECT configuracoes FROM `{services.TABLE_LOJA_CONFIG_DETALHES}` WHERE loja_id = @loja_id"
    job_config = services.bigquery.QueryJobConfig(query_parameters=[services.bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id)])
    results = [dict(row) for row in services.client.query(query, job_config=job_config)]
    
    if not results or not results[0].get('configuracoes'):
        return models.LojaConfigDetalhes()
    
    config_data = results[0]['configuracoes']
    if isinstance(config_data, str):
      try:
        config_data = services.json.loads(config_data)
      except services.json.JSONDecodeError:
        return models.LojaConfigDetalhes()

    if isinstance(config_data, dict):
        return models.LojaConfigDetalhes(**config_data)

    return models.LojaConfigDetalhes()
    
@router.post("/lojas/{loja_id}/detalhes", status_code=200)
async def save_loja_detalhes(loja_id: str, detalhes: models.LojaConfigDetalhes, user: dict = Depends(dependencies.get_current_user)):
    """Salva a configuração detalhada de uma loja específica."""
    merge_query = f"""
    MERGE `{services.TABLE_LOJA_CONFIG_DETALHES}` T
    USING (SELECT @loja_id as loja_id, @config_json as configuracoes) S ON T.loja_id = S.loja_id
    WHEN MATCHED THEN UPDATE SET T.configuracoes = S.configuracoes
    WHEN NOT MATCHED THEN INSERT (loja_id, configuracoes) VALUES (S.loja_id, S.configuracoes)
    """
    params = [
        services.bigquery.ScalarQueryParameter("loja_id", "STRING", loja_id),
        services.bigquery.ScalarQueryParameter("config_json", "JSON", detalhes.model_dump_json()),
    ]
    services.client.query(merge_query, job_config=services.bigquery.QueryJobConfig(query_parameters=params)).result()
    services.log_action(user.get('email'), "SAVE_STORE_DETAILS", {"loja_id": loja_id})
    return {"message": "Configurações salvas!"}
