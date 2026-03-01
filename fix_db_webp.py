import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('c:/Users/Public/Documents/Inmobiliarias.ai/backend/.env')

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

if not DATABASE_URL:
    print('No DATABASE_URL found')
else:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for col, table in [('image', 'properties'), ('thumbnail_url', 'properties'), ('image', 'developments'), ('thumbnail_url', 'developments'), ('avatar_url', 'users')]:
            conn.execute(
                text(f"UPDATE {table} SET {col} = REPLACE(REPLACE(REPLACE({col}, '.jpg', '.webp'), '.png', '.webp'), '.jpeg', '.webp') WHERE {col} ILIKE :jpg OR {col} ILIKE :png OR {col} ILIKE :jpeg;"),
                {"jpg": "%.jpg%", "png": "%.png%", "jpeg": "%.jpeg%"}
            )
            
        conn.execute(
            text("UPDATE properties SET gallery = replace(replace(replace(gallery::text, '.jpg', '.webp'), '.png', '.webp'), '.jpeg', '.webp')::json WHERE gallery::text ILIKE :jpg OR gallery::text ILIKE :png OR gallery::text ILIKE :jpeg;"),
            {"jpg": "%.jpg%", "png": "%.png%", "jpeg": "%.jpeg%"}
        )
        
        conn.execute(
            text("UPDATE developments SET gallery = replace(replace(replace(gallery::text, '.jpg', '.webp'), '.png', '.webp'), '.jpeg', '.webp')::json WHERE gallery::text ILIKE :jpg OR gallery::text ILIKE :png OR gallery::text ILIKE :jpeg;"),
            {"jpg": "%.jpg%", "png": "%.png%", "jpeg": "%.jpeg%"}
        )
        
    print('DB Migration to WEBP done!')
