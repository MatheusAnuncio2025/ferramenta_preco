# app/routers/auth.py
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from google.cloud import bigquery
from .. import services

router = APIRouter(
    tags=["Autenticação"]
)

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
    """Redireciona o usuário para a tela de login do Google."""
    redirect_uri = request.url_for('auth')
    request.session['auth_action'] = action
    return await oauth.google.authorize_redirect(request, str(redirect_uri), prompt='select_account')

@router.get('/auth')
async def auth(request: Request):
    """Endpoint de callback para o OAuth do Google."""
    user_db_data = None
    try:
        action = request.session.pop('auth_action', 'login')
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        user_email = user_info.get('email')
        if not user_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail não retornado pelo Google.")

        query = f"SELECT *, pode_ver_historico FROM `{services.TABLE_USUARIOS}` WHERE email = @email"
        params = [bigquery.ScalarQueryParameter("email", "STRING", user_email)]
        results = list(services.client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)))
        user_exists = len(results) > 0
        
        if action == 'login':
            if not user_exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário não cadastrado. Use o botão 'Cadastrar-se'.")
            user_db_data = dict(results[0])
            update_query = f"UPDATE `{services.TABLE_USUARIOS}` SET ultimo_login = @now WHERE email = @email"
            services.client.query(update_query, job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("now", "TIMESTAMP", services.datetime.utcnow()),
                bigquery.ScalarQueryParameter("email", "STRING", user_email)
            ])).result()
        
        elif action == 'register':
            if user_exists:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail já está cadastrado. Use o botão 'Entrar'.")
            new_user_row = {
                "email": user_email, "nome": user_info.get('name'), "foto_url": user_info.get('picture'),
                "autorizado": False, "funcao": "usuario", "telefone": None, "departamento": None,
                "data_cadastro": services.datetime.utcnow().isoformat(), "ultimo_login": services.datetime.utcnow().isoformat(),
                "pode_ver_historico": False
            }
            cols = ", ".join(f"`{k}`" for k in new_user_row.keys())
            placeholders = ", ".join(f"@{k}" for k in new_user_row.keys())
            insert_query = f"INSERT INTO `{services.TABLE_USUARIOS}` ({cols}) VALUES ({placeholders})"
            bq_params = [bigquery.ScalarQueryParameter(k, "BOOL" if isinstance(v, bool) else "STRING", v) for k, v in new_user_row.items()]
            services.client.query(insert_query, job_config=bigquery.QueryJobConfig(query_parameters=bq_params)).result()
            services.log_action(user_email, "NEW_USER_REGISTERED", {"source": "google_register"})
            user_db_data = new_user_row
        
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ação desconhecida.")

        if not user_db_data or not user_db_data.get('autorizado'):
            request.session['user'] = {'email': user_email, 'authorized': False}
            return RedirectResponse(url='/pendente', status_code=303)

        request.session['user'] = {
            'name': user_db_data.get('nome'), 'email': user_email,
            'picture': user_db_data.get('foto_url'), 'role': user_db_data.get('funcao'),
            'authorized': True, 'pode_ver_historico': user_db_data.get('pode_ver_historico', False)
        }
        services.log_action(user_email, "LOGIN_SUCCESS", {"action": action})
        return RedirectResponse(url='/calculadora', status_code=303)
        
    except Exception as e:
        services.traceback.print_exc()
        services.log_action("unknown", "AUTH_CALLBACK_FAILED", {"error": str(e)})
        request.session.pop('user', None)
        return RedirectResponse(url=f'/?error=Ocorreu um erro inesperado.', status_code=303)

@router.get('/logout')
async def logout(request: Request):
    """Faz o logout do usuário e limpa a sessão."""
    user_email = request.session.get('user', {}).get('email')
    if user_email:
        services.log_action(user_email, "LOGOUT")
    request.session.pop('user', None)
    return RedirectResponse(url='/', status_code=303)

@router.get("/api/auth/status")
async def auth_status(request: Request):
    """Verifica o status atual de autenticação do usuário."""
    user = request.session.get("user")
    return {"authenticated": True, **user} if user and user.get("authorized") else {"authenticated": False}
