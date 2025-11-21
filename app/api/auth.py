from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.db import get_db
from app.auth import authenticate_user, create_access_token
import logging
import traceback

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


@router.post(
    "/token",
    summary="Получить JWT-токен по логину и паролю",
    description="""
    Аутентификация пользователя по username и паролю. Возвращает JWT-токен для авторизации в системе.
    Используйте Content-Type: application/x-www-form-urlencoded.
    """,
    response_description="JWT access token и тип токена (bearer)",
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для получения JWT-токена по логину и паролю.
    Проверяет пользователя, возвращает access_token или ошибку 401.
    """
    try:
        logger.info(f"Попытка входа пользователя: {form_data.username}")
        user = await authenticate_user(db, form_data.username, form_data.password)
        if not user:
            logger.warning(f"Неуспешная попытка входа: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = create_access_token(data={"sub": user.username})
        logger.info(
            f"Пользователь {form_data.username} успешно аутентифицирован")
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при аутентификации: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при аутентификации: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")
