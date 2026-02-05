
from fastapi import APIRouter, HTTPException
import schemas, storage

router = APIRouter()

@router.post("/presigned-url")
def get_presigned_url(request: schemas.PresignedUrlRequest):
    data = storage.get_presigned_upload_url(request.filename, request.content_type)
    if not data: 
        raise HTTPException(status_code=500, detail="Error generating secure upload URL")
    return data
