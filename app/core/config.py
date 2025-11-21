import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# --- Класс конфигурации приложения ---


class Settings(BaseSettings):
    # --- Настройки базы данных ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:1111@localhost:5432/workflow_employee")  # Основная БД

    DATABASE_URL_TEST: str = os.getenv(
        "DATABASE_URL_TEST", "postgresql+asyncpg://postgres:1111@localhost:5432/workflow_employee_test")  # Тестовая БД

    # --- JWT ---
    # Секретный ключ для подписи JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key")
    ALGORITHM: str = "HS256"  # Алгоритм подписи JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Время жизни access-токена (минуты)

    # --- Первый суперпользователь ---
    FIRST_SUPERUSER_USERNAME: str = os.getenv(
        "FIRST_SUPERUSER_USERNAME", "admin")  # Логин первого суперпользователя
    FIRST_SUPERUSER_PASSWORD: str = os.getenv(
        "FIRST_SUPERUSER_PASSWORD", "admin_password")  # Пароль первого суперпользователя
    FIRST_SUPERUSER_FULL_NAME: str = os.getenv(
        "FIRST_SUPERUSER_FULL_NAME", "Admin User")  # Имя первого суперпользователя

    PROJECT_NAME: str = os.getenv(
        "PROJECT_NAME", "WORKFLOW_EMPLOYEE")  # Имя проекта
    
    class Config:
        case_sensitive = True  # Все переменные чувствительны к регистру


# Экземпляр настроек для использования в приложении
settings = Settings()
