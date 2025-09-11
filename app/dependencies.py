# app/dependencies.py
from fastapi import Request, Depends, HTTPException, status

async def get_current_user(request: Request):
    """
    Lê o usuário da sessão e valida autorização.
    Aceita 'authorized' ou 'autorizado' por compatibilidade.
    """
    user = request.session.get('user') or {}
    autorizado = user.get('authorized')
    if autorizado is None:
        autorizado = user.get('autorizado')
    if not autorizado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado ou não autorizado."
        )
    return user

async def get_current_admin_user(user: dict = Depends(get_current_user)):
    """
    Restringe a administradores. Aceita 'role' ou 'funcao'.
    """
    role = user.get('role') or user.get('funcao') or 'usuario'
    if role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores."
        )
    return user

async def get_historico_viewer_user(user: dict = Depends(get_current_user)):
    """
    Garante permissão para visualizar o histórico.
    """
    if not user.get('pode_ver_historico'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Você não tem permissão para visualizar o histórico."
        )
    return user
