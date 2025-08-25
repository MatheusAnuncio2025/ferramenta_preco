# app/dependencies.py
from fastapi import Request, Depends, HTTPException, status

async def get_current_user(request: Request):
    """
    Dependency function to get the current user from the session.
    Raises HTTPException 401 if the user is not authenticated or authorized.
    """
    user = request.session.get('user')
    if not user or not user.get('authorized'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado ou não autorizado."
        )
    return user

async def get_current_admin_user(user: dict = Depends(get_current_user)):
    """
    Dependency function to ensure the current user has an 'admin' role.
    Raises HTTPException 403 if the user is not an admin.
    """
    if user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Acesso restrito a administradores."
        )
    return user

async def get_historico_viewer_user(user: dict = Depends(get_current_user)):
    """
    Dependency function to ensure the user has permission to view history.
    Raises HTTPException 403 if the user lacks permission.
    """
    if not user.get('pode_ver_historico'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Você não tem permissão para visualizar o histórico."
        )
    return user
