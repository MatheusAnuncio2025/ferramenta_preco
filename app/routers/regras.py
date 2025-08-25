# app/routers/regras.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import models, services, dependencies
import uuid

router = APIRouter(
    prefix="/api/regras-negocio",
    tags=["Regras de Negócio"]
)

# --- GET (Leitura) ---

@router.get("")
async def get_regras_negocio(user: dict = Depends(dependencies.get_current_user)):
    """Recupera todas as regras de negócio."""
    try:
        return services.get_all_business_rules()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar regras: {e}")

# --- Endpoints para Regras de Tarifa Fixa ---

@router.post("/tarifa-fixa", response_model=models.RegraTarifaFixa, status_code=status.HTTP_201_CREATED)
async def create_regra_tarifa_fixa(regra: models.RegraTarifaFixa, user: dict = Depends(dependencies.get_current_admin_user)):
    """Cria uma nova regra de tarifa fixa (Apenas Admin)."""
    try:
        regra.id = str(uuid.uuid4())
        row_to_insert = regra.model_dump()
        
        cols = ", ".join(f"`{k}`" for k in row_to_insert.keys())
        placeholders = ", ".join(f"@{k}" for k in row_to_insert.keys())
        query = f"INSERT INTO `{services.TABLE_REGRAS_TARIFA_FIXA}` ({cols}) VALUES ({placeholders})"
        
        params = [services.bigquery.ScalarQueryParameter(k, "STRING" if v is None else "NUMERIC" if isinstance(v, (float, int)) else "STRING", v) for k, v in row_to_insert.items()]
        
        services.execute_query(query, params)
        services.log_action(user['email'], "CREATE_BUSINESS_RULE", {"rule_type": "TARIFA_FIXA", "rule_id": regra.id})
        return regra
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/tarifa-fixa/{rule_id}", response_model=models.RegraTarifaFixa)
async def update_regra_tarifa_fixa(rule_id: str, regra: models.RegraTarifaFixa, user: dict = Depends(dependencies.get_current_admin_user)):
    """Atualiza uma regra de tarifa fixa existente (Apenas Admin)."""
    try:
        regra.id = rule_id
        update_data = regra.model_dump(exclude={'id'})
        
        set_clauses = ", ".join([f"`{k}` = @{k}" for k in update_data.keys()])
        query = f"UPDATE `{services.TABLE_REGRAS_TARIFA_FIXA}` SET {set_clauses} WHERE id = @id"

        params = [services.bigquery.ScalarQueryParameter("id", "STRING", rule_id)]
        params.extend([services.bigquery.ScalarQueryParameter(k, "STRING" if v is None else "NUMERIC" if isinstance(v, (float, int)) else "STRING", v) for k, v in update_data.items()])

        services.execute_query(query, params)
        services.log_action(user['email'], "UPDATE_BUSINESS_RULE", {"rule_type": "TARIFA_FIXA", "rule_id": rule_id})
        return regra
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/tarifa-fixa/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_regra_tarifa_fixa(rule_id: str, user: dict = Depends(dependencies.get_current_admin_user)):
    """Exclui uma regra de tarifa fixa (Apenas Admin)."""
    try:
        query = f"DELETE FROM `{services.TABLE_REGRAS_TARIFA_FIXA}` WHERE id = @id"
        params = [services.bigquery.ScalarQueryParameter("id", "STRING", rule_id)]
        services.execute_query(query, params)
        services.log_action(user['email'], "DELETE_BUSINESS_RULE", {"rule_type": "TARIFA_FIXA", "rule_id": rule_id})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Endpoints para Categorias de Precificação ---

@router.post("/categorias", response_model=models.CategoriaPrecificacao, status_code=status.HTTP_201_CREATED)
async def create_categoria(categoria: models.CategoriaPrecificacao, user: dict = Depends(dependencies.get_current_admin_user)):
    """Cria uma nova categoria de precificação (Apenas Admin)."""
    try:
        categoria.id = str(uuid.uuid4())
        row_to_insert = categoria.model_dump()
        cols = ", ".join(f"`{k}`" for k in row_to_insert.keys())
        placeholders = ", ".join(f"@{k}" for k in row_to_insert.keys())
        query = f"INSERT INTO `{services.TABLE_CATEGORIAS_PRECIFICACAO}` ({cols}) VALUES ({placeholders})"
        params = [services.bigquery.ScalarQueryParameter(k, "STRING" if v is None else "NUMERIC" if isinstance(v, (float, int)) else "STRING", v) for k, v in row_to_insert.items()]
        services.execute_query(query, params)
        services.log_action(user['email'], "CREATE_BUSINESS_RULE", {"rule_type": "CATEGORIA", "rule_id": categoria.id})
        return categoria
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/categorias/{rule_id}", response_model=models.CategoriaPrecificacao)
async def update_categoria(rule_id: str, categoria: models.CategoriaPrecificacao, user: dict = Depends(dependencies.get_current_admin_user)):
    """Atualiza uma categoria de precificação (Apenas Admin)."""
    try:
        categoria.id = rule_id
        update_data = categoria.model_dump(exclude={'id'})
        set_clauses = ", ".join([f"`{k}` = @{k}" for k in update_data.keys()])
        query = f"UPDATE `{services.TABLE_CATEGORIAS_PRECIFICACAO}` SET {set_clauses} WHERE id = @id"
        params = [services.bigquery.ScalarQueryParameter("id", "STRING", rule_id)]
        params.extend([services.bigquery.ScalarQueryParameter(k, "STRING" if v is None else "NUMERIC" if isinstance(v, (float, int)) else "STRING", v) for k, v in update_data.items()])
        services.execute_query(query, params)
        services.log_action(user['email'], "UPDATE_BUSINESS_RULE", {"rule_type": "CATEGORIA", "rule_id": rule_id})
        return categoria
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/categorias/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_categoria(rule_id: str, user: dict = Depends(dependencies.get_current_admin_user)):
    """Exclui uma categoria de precificação (Apenas Admin)."""
    try:
        query = f"DELETE FROM `{services.TABLE_CATEGORIAS_PRECIFICACAO}` WHERE id = @id"
        params = [services.bigquery.ScalarQueryParameter("id", "STRING", rule_id)]
        services.execute_query(query, params)
        services.log_action(user['email'], "DELETE_BUSINESS_RULE", {"rule_type": "CATEGORIA", "rule_id": rule_id})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Endpoints para Regras de Frete ---

@router.post("/frete", response_model=models.RegraFrete, status_code=status.HTTP_201_CREATED)
async def create_regra_frete(regra: models.RegraFrete, user: dict = Depends(dependencies.get_current_admin_user)):
    """Cria uma nova regra de frete (Apenas Admin)."""
    try:
        regra.id = str(uuid.uuid4())
        row_to_insert = regra.model_dump()
        cols = ", ".join(f"`{k}`" for k in row_to_insert.keys())
        placeholders = ", ".join(f"@{k}" for k in row_to_insert.keys())
        query = f"INSERT INTO `{services.TABLE_REGRAS_FRETE}` ({cols}) VALUES ({placeholders})"
        params = [services.bigquery.ScalarQueryParameter(k, "STRING" if v is None else "NUMERIC" if isinstance(v, (float, int)) else "STRING", v) for k, v in row_to_insert.items()]
        services.execute_query(query, params)
        services.log_action(user['email'], "CREATE_BUSINESS_RULE", {"rule_type": "FRETE", "rule_id": regra.id})
        return regra
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/frete/{rule_id}", response_model=models.RegraFrete)
async def update_regra_frete(rule_id: str, regra: models.RegraFrete, user: dict = Depends(dependencies.get_current_admin_user)):
    """Atualiza uma regra de frete (Apenas Admin)."""
    try:
        regra.id = rule_id
        update_data = regra.model_dump(exclude={'id'})
        set_clauses = ", ".join([f"`{k}` = @{k}" for k in update_data.keys()])
        query = f"UPDATE `{services.TABLE_REGRAS_FRETE}` SET {set_clauses} WHERE id = @id"
        params = [services.bigquery.ScalarQueryParameter("id", "STRING", rule_id)]
        params.extend([services.bigquery.ScalarQueryParameter(k, "STRING" if v is None else "NUMERIC" if isinstance(v, (float, int)) else "STRING", v) for k, v in update_data.items()])
        services.execute_query(query, params)
        services.log_action(user['email'], "UPDATE_BUSINESS_RULE", {"rule_type": "FRETE", "rule_id": rule_id})
        return regra
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/frete/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_regra_frete(rule_id: str, user: dict = Depends(dependencies.get_current_admin_user)):
    """Exclui uma regra de frete (Apenas Admin)."""
    try:
        query = f"DELETE FROM `{services.TABLE_REGRAS_FRETE}` WHERE id = @id"
        params = [services.bigquery.ScalarQueryParameter("id", "STRING", rule_id)]
        services.execute_query(query, params)
        services.log_action(user['email'], "DELETE_BUSINESS_RULE", {"rule_type": "FRETE", "rule_id": rule_id})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))