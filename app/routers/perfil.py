from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from .. import models, services, dependencies

router = APIRouter(
    prefix="/api/perfil",
    tags=["Perfil do Usuário"]
)

@router.get("/meus-dados", response_model=models.UserProfile)
async def get_my_profile_data(user: dict = Depends(dependencies.get_current_user)):
    user_data = services.get_user_by_email(user['email'])
    if not user_data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    for key, value in list(user_data.items()):
        if hasattr(value, "isoformat"):
            user_data[key] = value.isoformat()
    return user_data

@router.post("/meus-dados", status_code=200)
async def update_my_profile_data(update_data: models.UserProfileUpdate, user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    updates = {"telefone": update_data.telefone, "departamento": update_data.departamento}
    services.update_user_properties(user_email, updates)
    services.log_action(user_email, "PROFILE_UPDATED", updates)
    return {"message": "Perfil atualizado com sucesso"}

@router.post("/upload-foto")
async def upload_profile_picture(request: Request, file: UploadFile = File(...), user: dict = Depends(dependencies.get_current_user)):
    user_email = user.get('email')
    if not services.BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Bucket de armazenamento não configurado.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não suportado. Use JPG, PNG ou WEBP.")
    max_size = 2 * 1024 * 1024
    pos = file.file.tell(); file.file.seek(0, 2); size = file.file.tell(); file.file.seek(pos, 0)
    if size > max_size:
        raise HTTPException(status_code=400, detail="Arquivo maior que 2 MB.")
    try:
        bucket = services.storage_client.bucket(services.BUCKET_NAME)
        ext = services.os.path.splitext(file.filename)[1]
        blob_name = f"profile_photos/{user_email}_{services.uuid.uuid4()}{ext}"
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, content_type=file.content_type)
        blob.make_public()
        new_photo_url = blob.public_url
        services.update_user_properties(user_email, {"foto_url": new_photo_url})
        if 'user' in request.session:
            request.session['user']['picture'] = new_photo_url
            request.session.modified = True
        services.log_action(user_email, "PROFILE_PHOTO_UPLOADED")
        return {"new_photo_url": new_photo_url}
    except Exception as e:
        services.log_action(user_email, "PROFILE_PHOTO_UPLOAD_FAILED", {"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Erro no upload da foto: {e}")
