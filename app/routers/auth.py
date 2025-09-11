from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
import traceback
from .. import services

router = APIRouter(tags=["Autenticação"])

config = Config()
oauth = OAuth(config)
oauth.register(
    name='google',
    client_id=services.os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=services.os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

@router.get('/login')
async def login(request: Request, action: str = 'login'):
    redirect_uri = request.url_for('auth')
    request.session['auth_action'] = action
    return await oauth.google.authorize_redirect(request, str(redirect_uri), prompt='select_account')

@router.get('/auth')
async def auth(request: Request):
    try:
        action = request.session.pop('auth_action', 'login')
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        user_email = user_info.get('email')
        if not user_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail não retornado pelo Google.")

        user_db_data = services.get_user_by_email(user_email)

        if action == 'login':
            if not user_db_data:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário não cadastrado. Use 'Cadastrar-se'.")
            services.update_user_properties(user_email, {"ultimo_login": services.datetime.utcnow().isoformat()})
        elif action == 'register':
            if user_db_data:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail já está cadastrado. Use 'Entrar'.")
            new_user_row = {
                "email": user_email,
                "nome": user_info.get('name'),
                "foto_url": user_info.get('picture'),
                "autorizado": False,
                "funcao": "usuario",
                "telefone": None,
                "departamento": None,
                "data_cadastro": services.datetime.utcnow().isoformat(),
                "ultimo_login": services.datetime.utcnow().isoformat(),
                "pode_ver_historico": False
            }
            user_db_data = services.create_user(new_user_row)
            services.log_action(user_email, "NEW_USER_REGISTERED", {"source": "google_register"})
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ação desconhecida.")

        if not user_db_data or not user_db_data.get('autorizado'):
            request.session['user'] = {'email': user_email, 'authorized': False}
            return RedirectResponse(url='/pendente', status_code=303)

        user_db_data_updated = services.get_user_by_email(user_email)
        request.session['user'] = {
            'name': user_db_data_updated.get('nome'),
            'email': user_email,
            'picture': user_db_data_updated.get('foto_url'),
            'role': user_db_data_updated.get('funcao'),
            'authorized': True,
            'pode_ver_historico': user_db_data_updated.get('pode_ver_historico', False),
        }
        services.log_action(user_email, "LOGIN_SUCCESS", {"action": action})
        return RedirectResponse(url='/calculadora', status_code=303)
    except Exception as e:
        traceback.print_exc()
        services.log_action("unknown", "AUTH_CALLBACK_FAILED", {"error": str(e)})
        request.session.pop('user', None)
        error_message = getattr(e, 'detail', 'Ocorreu um erro ao autenticar. Tente novamente.')
        return RedirectResponse(url=f'/?error={error_message}', status_code=303)

@router.get('/logout')
async def logout(request: Request):
    user_email = request.session.get('user', {}).get('email')
    if user_email:
        services.log_action(user_email, "LOGOUT")
    request.session.pop('user', None)
    return RedirectResponse(url='/', status_code=303)

@router.get("/api/auth/status")
async def auth_status(request: Request):
    user = request.session.get("user")
    return {"authenticated": True, **user} if user and user.get("authorized") else {"authenticated": False}