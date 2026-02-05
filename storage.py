
import os
from minio import Minio
from datetime import timedelta
import uuid

# 1. Configuración de Red Interna (Backend -> MinIO)
# Cambiamos de propcrm_miniost a propcrm-miniost ya que los underscores (_) causan 'Invalid Hostname' en S3
MINIO_HOST_INTERNAL = os.getenv("MINIO_HOST_INTERNAL", "propcrm-miniost:9000")
# Fallback al que vimos en tu captura si el anterior falla (aunque el underscore es el problema)
MINIO_HOST_ALT = "propcrm_miniost:9000"

MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "crm")

# 2. Configuración de Red Pública (Navegador -> MinIO)
MINIO_PUBLIC_DOMAIN = os.getenv("MINIO_ENDPOINT", "propcrm-miniost.rjcuax.easypanel.host")

def get_minio_client(internal=True):
    """
    Retorna un cliente de MinIO. 
    Si internal=True, usa la red de Docker (sin SSL, puerto 9000).
    Si internal=False, usa el dominio público (con SSL).
    """
    host = MINIO_HOST_INTERNAL if internal else MINIO_PUBLIC_DOMAIN
    return Minio(
        host,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=not internal, # False para red interna, True para pública
        region="us-east-1" # Agregamos region explícita para evitar que intente conectar para buscar la región
    )

# Cliente global para operaciones del backend (usa red interna)
minio_client = get_minio_client(internal=True)

def get_presigned_upload_url(filename: str, content_type: str):
    try:
        ext = filename.split('.')[-1] if '.' in filename else 'bin'
        object_name = f"uploads/{uuid.uuid4()}.{ext}"

        # Para el link que usa el navegador (browser), necesitamos el cliente PÚBLICO
        public_client = get_minio_client(internal=False)

        upload_url = public_client.presigned_put_object(
            MINIO_BUCKET,
            object_name,
            expires=timedelta(minutes=10),
        )

        public_url = f"https://{MINIO_PUBLIC_DOMAIN}/{MINIO_BUCKET}/{object_name}"

        return {
            "upload_url": upload_url,
            "public_url": public_url,
            "object_name": object_name
        }
    except Exception as e:
        print(f"Error generando Presigned URL: {e}")
        return None
