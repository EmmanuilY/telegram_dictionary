from dotenv import load_dotenv
from pydantic import BaseSettings

load_dotenv()  # Загрузка переменных окружения из .env файла


class Settings(BaseSettings):
    # Настройки доступа к БД
    USER: str = "postgres"
    PASSWORD: str = "postgres"
    DATABASE: str = "postgres"
    HOST: str = "postgres"
    BOT_TOKEN: str = 'SecretStr'

    class Config:
        env_file = ".env"


settings = Settings()
