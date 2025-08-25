# app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from google.cloud import bigquery
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)

@router.get("/usuarios", response_model=List[models.UserProfile])
async def list_all_users(user: dict = Depends(dependencies.get_current_admin_user)):
    """Lista todos os usuários no sistema."""
    query = f"SELECT *, pode_ver_historico FROM `{services.TABLE_USUARIOS}` ORDER BY nome ASC"
    results = [dict(row) for row in services.client.query(query)]
    for user_data in results:
        for key, value in user_data.items():
            if isinstance(value, (services.datetime, services.date)):
                user_data[key] = value.isoformat()
    return results

@router.post("/usuarios", response_model=models.UserProfile, status_code=201)
async def add_new_user_by_admin(payload: models.NewUserPayload, admin: dict = Depends(dependencies.get_current_admin_user)):
    """Adiciona um novo usuário ao sistema (Apenas Admin)."""
    target_email = payload.email
    query = f"SELECT email FROM `{services.TABLE_USUARIOS}` WHERE email = @email"
    if list(services.client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("email", "STRING", target_email)]))):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Usuário com email {target_email} já existe.")
    
    new_user_row = {
        "email": target_email, "nome": payload.nome, "foto_url": f"https://ui-avatars.com/api/?name={payload.nome.replace(' ', '+')}&background=random",
        "autorizado": payload.autorizado, "funcao": payload.funcao,
        "data_cadastro": services.datetime.utcnow().isoformat(),
        "pode_ver_historico": False
    }

    cols = ", ".join(f"`{k}`" for k in new_user_row.keys())
    placeholders = ", ".join(f"@{k}" for k in new_user_row.keys())
    insert_query = f"INSERT INTO `{services.TABLE_USUARIOS}` ({cols}) VALUES ({placeholders})"
    
    bq_params = [bigquery.ScalarQueryParameter(key, "BOOL" if isinstance(value, bool) else "STRING", value) for key, value in new_user_row.items()]
    
    services.client.query(insert_query, job_config=bigquery.QueryJobConfig(query_parameters=bq_params)).result()

    services.log_action(admin.get('email'), "ADMIN_ADDED_USER", {"new_user_email": target_email})
    return new_user_row

@router.post("/usuarios/{target_email}/acao", status_code=200)
async def manage_user(target_email: str, acao: str, valor: Optional[str] = None, admin: dict = Depends(dependencies.get_current_admin_user)):
    """Gerencia propriedades do usuário como função e autorização (Apenas Admin)."""
    if admin.get('email') == target_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administradores não podem alterar a própria função ou status.")
    
    field_to_update = None
    param_value = valor
    param_type = "STRING"

    if acao == 'funcao' and valor in ['admin', 'usuario']:
        field_to_update = 'funcao'
    elif acao == 'autorizar' and valor in ['true', 'false']:
        field_to_update = 'autorizado'
        param_value = (valor == 'true')
        param_type = "BOOL"
    elif acao == 'pode_ver_historico' and valor in ['true', 'false']:
        field_to_update = 'pode_ver_historico'
        param_value = (valor == 'true')
        param_type = "BOOL"
    
    if not field_to_update:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ação ou valor inválido.")

    query = f"UPDATE `{services.TABLE_USUARIOS}` SET {field_to_update} = @valor WHERE email = @email"
    params = [
        bigquery.ScalarQueryParameter("valor", param_type, param_value),
        bigquery.ScalarQueryParameter("email", "STRING", target_email)
    ]
    services.client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    services.log_action(admin.get('email'), "ADMIN_MANAGED_USER", {"target": target_email, "action": acao, "value": valor})
    return {"message": "Usuário atualizado com sucesso."}

@router.delete("/usuarios/{target_email}", status_code=204)
async def delete_user(target_email: str, admin: dict = Depends(dependencies.get_current_admin_user)):
    """Deleta um usuário do sistema (Apenas Admin)."""
    if admin.get('email') == target_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administradores não podem se auto-excluir.")
    
    query = f"DELETE FROM `{services.TABLE_USUARIOS}` WHERE email = @email"
    params = [bigquery.ScalarQueryParameter("email", "STRING", target_email)]
    services.client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
    services.log_action(admin.get('email'), "ADMIN_DELETED_USER", {"target": target_email})
