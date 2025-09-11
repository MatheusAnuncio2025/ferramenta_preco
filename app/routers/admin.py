from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)

@router.get("/usuarios", response_model=List[models.UserProfile])
async def list_all_users(user: dict = Depends(dependencies.get_current_admin_user)):
    return services.get_all_users()

@router.post("/usuarios", response_model=models.UserProfile, status_code=201)
async def add_new_user_by_admin(payload: models.NewUserPayload, admin: dict = Depends(dependencies.get_current_admin_user)):
    target_email = payload.email
    if services.get_user_by_email(target_email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Usuário com email {target_email} já existe.")
    new_user_row = {
        "email": target_email,
        "nome": payload.nome,
        "foto_url": f"https://ui-avatars.com/api/?name={payload.nome.replace(' ', '+')}&background=random",
        "autorizado": payload.autorizado,
        "funcao": payload.funcao,
        "data_cadastro": services.datetime.utcnow().isoformat(),
        "pode_ver_historico": False
    }
    created_user = services.create_user(new_user_row)
    if not created_user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha ao criar o usuário.")
    services.log_action(admin.get('email'), "ADMIN_ADDED_USER", {"new_user_email": target_email})
    return created_user

@router.post("/usuarios/{target_email}/acao", status_code=200)
async def manage_user(target_email: str, acao: str, valor: Optional[str] = None, admin: dict = Depends(dependencies.get_current_admin_user)):
    if admin.get('email') == target_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administradores não podem alterar a própria função/status.")
    updates = {}
    if acao == 'funcao' and valor in ['admin', 'usuario']:
        updates['funcao'] = valor
    elif acao == 'autorizar' and valor in ['true', 'false']:
        updates['autorizado'] = (valor == 'true')
    elif acao == 'pode_ver_historico' and valor in ['true', 'false']:
        updates['pode_ver_historico'] = (valor == 'true')
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ação ou valor inválido.")
    services.update_user_properties(target_email, updates)
    services.log_action(admin.get('email'), "ADMIN_MANAGED_USER", {"target": target_email, "action": acao, "value": valor})
    return {"message": "Usuário atualizado com sucesso."}

@router.delete("/usuarios/{target_email}", status_code=204)
async def delete_user(target_email: str, admin: dict = Depends(dependencies.get_current_admin_user)):
    if admin.get('email') == target_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administradores não podem se auto-excluir.")
    if not services.get_user_by_email(target_email):
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    services.delete_user_by_email(target_email)
    services.log_action(admin.get('email'), "ADMIN_DELETED_USER", {"target": target_email})