import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "sqlite:///./test.db"
    secret_key: str = "super_secret_key_change_me_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    
    # Supabase / S3
    bucket_endpoint: Optional[str] = None
    bucket_access_key: Optional[str] = None
    bucket_secret_key: Optional[str] = None
    bucket_region: Optional[str] = None
    bucket_name: Optional[str] = None
    
    # Evolution API
    evolution_api_url: Optional[str] = None
    evolution_api_key: Optional[str] = None
    webhook_url: Optional[str] = None
    
    # Google & OpenAI
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
