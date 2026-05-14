from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field


class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Aitunnel / OpenAI (общий для всех бизнесов)
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_base_url: str = Field(..., env="OPENAI_BASE_URL")
    ai_model: str = Field(default="claude-haiku-4.5", env="AI_MODEL")
    
    # Admin
    admin_ids: List[int] = Field(..., env="ADMIN_IDS")
    
    # Follow-up
    followup_delay_seconds: int = Field(default=3600, env="FOLLOWUP_DELAY_SECONDS")
    
    # AI settings
    max_tokens: int = Field(default=500, env="MAX_TOKENS")
    ai_temperature: float = Field(default=0.7, env="AI_TEMPERATURE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()