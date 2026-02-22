import os
import sys
import base64
import uuid
import json
import mimetypes
from io import BytesIO

# Añadir el auth del sistema de django/fastapi
from database import SessionLocal
import models
from storage import get_minio_client, MINIO_BUCKET, MINIO_PUBLIC_DOMAIN

minio_client = get_minio_client(internal=True)

def upload_base64_to_minio(base64_str, folder="uploads"):
    if not isinstance(base64_str, str) or not base64_str.startswith("data:image"):
        return base64_str  # Ya es un link o es otra cosa

    try:
        header, encoded = base64_str.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]
        ext = mimetypes.guess_extension(mime_type) or ".jpg"
        
        file_data = base64.b64decode(encoded)
        file_stream = BytesIO(file_data)
        
        object_name = f"{folder}/{uuid.uuid4()}{ext}"
        
        minio_client.put_object(
            MINIO_BUCKET,
            object_name,
            file_stream,
            length=len(file_data),
            content_type=mime_type
        )
        
        public_url = f"https://{MINIO_PUBLIC_DOMAIN}/{MINIO_BUCKET}/{object_name}"
        return public_url
    except Exception as e:
        print(f"Error procesando base64: {e}")
        return base64_str

db = SessionLocal()

# 1. Configs
print("Migrando configuraciones...")
configs = db.query(models.AgencyConfig).all()
for c in configs:
    updated = False
    if c.logo_url and isinstance(c.logo_url, str) and c.logo_url.startswith("data:image"):
        print(f"Migrando logo config ID {c.id}")
        c.logo_url = upload_base64_to_minio(c.logo_url, "configs")
        updated = True
    if c.watermark_url and isinstance(c.watermark_url, str) and c.watermark_url.startswith("data:image"):
        print(f"Migrando watermark config ID {c.id}")
        c.watermark_url = upload_base64_to_minio(c.watermark_url, "configs")
        updated = True
    if updated:
        db.commit()

# 2. Properties
print("Migrando propiedades (images y gallery)...")
props = db.query(models.Property).all()
for p in props:
    updated = False
    if p.image and isinstance(p.image, str) and p.image.startswith("data:image"):
        print(f"Migrando imagen principal de propiedad {p.id}")
        p.image = upload_base64_to_minio(p.image, "properties")
        updated = True
    
    if p.gallery and isinstance(p.gallery, list):
        new_gallery = []
        for g_item in p.gallery:
            if isinstance(g_item, str) and g_item.startswith("data:image"):
                print(f"Migrando item de galeria propiedad {p.id}")
                new_url = upload_base64_to_minio(g_item, "properties")
                new_gallery.append(new_url)
                updated = True
            elif isinstance(g_item, dict) and "url" in g_item and g_item["url"].startswith("data:image"):
               print(f"Migrando item de galeria dict en propiedad {p.id}")
               g_item["url"] = upload_base64_to_minio(g_item["url"], "properties")
               new_gallery.append(g_item)
               updated = True
            else:
                new_gallery.append(g_item)
        if updated:
            p.gallery = new_gallery

    if updated:
        db.commit()

# Devs
print("Migrando emprendimientos...")
devs = db.query(models.Development).all()
for dev in devs:
    updated = False
    if dev.gallery and isinstance(dev.gallery, list):
        new_gallery = []
        for g_item in dev.gallery:
            if isinstance(g_item, str) and g_item.startswith("data:image"):
                print(f"Migrando item galeria dev {dev.id}")
                new_url = upload_base64_to_minio(g_item, "developments")
                new_gallery.append(new_url)
                updated = True
            elif isinstance(g_item, dict) and "url" in g_item and g_item["url"].startswith("data:image"):
               print(f"Migrando item de galeria dict dev {dev.id}")
               g_item["url"] = upload_base64_to_minio(g_item["url"], "developments")
               new_gallery.append(g_item)
               updated = True
            else:
                new_gallery.append(g_item)
        if updated:
            dev.gallery = new_gallery
            db.commit()


# Users
print("Migrando avatars...")
users = db.query(models.User).all()
for u in users:
    if u.avatar_url and isinstance(u.avatar_url, str) and u.avatar_url.startswith("data:image"):
        print(f"Migrando avatar user {u.id}")
        u.avatar_url = upload_base64_to_minio(u.avatar_url, "avatars")
        db.commit()

print("Migracion base64 completada.")
