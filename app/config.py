from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host_uid: int = 1000
    host_gid: int = 1000
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    redis_url: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
