from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/payments"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = "secret"


settings = Settings()
