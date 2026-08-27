from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DEVICE_TOKEN_EXPIRE_DAYS: int = 30
    AUTH_REQUIRED: bool = True
    MEDIA_ROOT: str = "storage/media"
    MEDIA_MAX_SIZE_BYTES: int = 104857600
    PHOTO_MAX_SIZE_BYTES: int = 10485760
    MEDIA_TTL_DAYS: int = 7
    PUSH_ENABLED: bool = False
    FCM_PROJECT_ID: str | None = None
    FCM_SERVICE_ACCOUNT_FILE: str | None = None
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str | None = None
    ADMIN_SESSION_SECRET: str | None = None
    ADMIN_ACTOR_DEVICE_ID: str | None = None

settings = Settings()
