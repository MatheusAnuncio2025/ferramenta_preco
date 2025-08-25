# app/routers/perfil.py
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/perfil",
    tags=["Perfil do Usuário"]
)

@router.get("/meus-dados", response_model=models.UserProfile)
async def get_my_profile_data(user: dict = Depends(dependencies.get_current_user)):
    """Recupera os dados de perfil do usuário logado."""
    query = f"SELECT * FROM `{services.TABLE_USUARIOS}` WHERE email = @email"
    job_config = services.bigquery.QueryJobConfig(query_parameters=[services.bigquery.ScalarQueryParameter("email", "STRING", user['email'])])
    results = [dict(row) for row in services.client.query(query, job_config=job_config)]
    if not results:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    user_data = results[0]
    for key, value in user_data.items():
        if isinstance(value, (services.datetime, services.date)):
            user_data[key] = value.isoformat()
    
    return user_data

@router.post("/meus-dados", status_code=200)
async def update_my_profile_data(update_data: models.UserProfileUpdate, user: dict = Depends(dependencies.get_current_user)):
    """Atualiza os dados de perfil do usuário logado."""
    user_email = user.get('email')
    query = f"""
        UPDATE `{services.TABLE_USUARIOS}`
        SET telefone = @telefone, departamento = @departamento
        WHERE email = @email
    """
    params = [
        services.bigquery.ScalarQueryParameter("telefone", "STRING", update_data.telefone),
        services.bigquery.ScalarQueryParameter("departamento", "STRING", update_data.departamento),
        services.bigquery.ScalarQueryParameter("email", "STRING", user_email),
    ]
    services.client.query(query, job_config=services.bigquery.QueryJobConfig(query_parameters=params)).result()
    services.log_action(user_email, "PROFILE_UPDATED", {"telefone": update_data.telefone, "departamento": update_data.departamento})
    return {"message": "Perfil atualizado com sucesso"}

@router.post("/upload-foto")
async def upload_profile_picture(request: Request, file: UploadFile = File(...), user: dict = Depends(dependencies.get_current_user)):
    """Faz o upload de uma nova foto de perfil para o usuário logado."""
    user_email = user.get('email')
    if not services.BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Bucket de armazenamento não configurado.")
    try:
        bucket = services.storage_client.bucket(services.BUCKET_NAME)
        ext = services.os.path.splitext(file.filename)[1]
        blob_name = f"profile_photos/{user_email}_{services.uuid.uuid4()}{ext}"
        blob = bucket.blob(blob_name)
        
        blob.upload_from_file(file.file, content_type=file.content_type)
        
        # Tornar o blob público para obter uma URL acessível
        blob.make_public()
        new_photo_url = blob.public_url

        query = f"UPDATE `{services.TABLE_USUARIOS}` SET foto_url = @url WHERE email = @email"
        params = [services.bigquery.ScalarQueryParameter("url", "STRING", new_photo_url), services.bigquery.ScalarQueryParameter("email", "STRING", user_email)]
        services.client.query(query, job_config=services.bigquery.QueryJobConfig(query_parameters=params)).result()
        
        # Atualiza a URL da foto na sessão do usuário
        if 'user' in request.session:
            request.session['user']['picture'] = new_photo_url
            # Força o salvamento da sessão
            request.session.modified = True


        services.log_action(user_email, "PROFILE_PHOTO_UPLOADED")
        return {"new_photo_url": new_photo_url}
    except Exception as e:
        services.log_action(user_email, "PROFILE_PHOTO_UPLOAD_FAILED", {"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Erro no upload da foto: {e}")
