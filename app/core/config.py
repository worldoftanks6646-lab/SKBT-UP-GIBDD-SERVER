from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MEDIA_ROOT: str = "storage/media"
    MEDIA_MAX_SIZE_BYTES: int = 104857600
    MEDIA_TTL_DAYS: int = 7

settings = Settings()
