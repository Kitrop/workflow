from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from typing import List
from app.db import get_db
from app.auth import get_current_user
from app.schemas.user import UserOut, UserCreate, UserUpdate
from app.models.user import User
from app.crud import user as crud_user
import logging
import traceback

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

# --- Проверка роли администратора ---


def is_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        logger.warning(
            f"Попытка доступа без прав администратора: {user.username}")
        raise HTTPException(status_code=403, detail="Требуется роль admin")
    return user

# --- Получить информацию о себе ---


@router.get(
    "/me",
    response_model=UserOut,
    summary="Получить информацию о себе",
    description="""
    Возвращает информацию о текущем пользователе на основе JWT-токена.
    """
)
async def read_users_me(current_user: User = Depends(get_current_user)):
    try:
        logger.info(
            f"Пользователь {current_user.username} запросил информацию о себе")
        return UserOut.model_validate(current_user)
    except Exception as e:
        logger.error(
            f"Ошибка при получении информации о пользователе: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Создать нового пользователя (только для админов) ---


@router.post(
    "/",
    response_model=UserOut,
    dependencies=[Depends(is_admin)],
    status_code=status.HTTP_201_CREATED,
    summary="Создать нового пользователя",
    description="""
    Создание нового пользователя (только для админов). Если пользователь с таким username уже существует, будет возвращена ошибка.
    """
)
async def create_user_view(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        logger.info(f"Создание пользователя: {user_in.username}")
        existing = await crud_user.get_user_by_username(db, user_in.username)
        if existing:
            logger.warning(
                f"Попытка создать уже существующего пользователя: {user_in.username}")
            raise HTTPException(
                status_code=400, detail="Пользователь уже существует")
        user = await crud_user.create_user(db, user_in)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Пользователь {user.username} успешно создан")
        return UserOut.model_validate(user)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при создании пользователя: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при создании пользователя: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить список пользователей (только для авторизованных пользователей) ---


@router.get(
    "/",
    response_model=List[UserOut],
    summary="Получить список пользователей",
    description="""
    Получение списка всех пользователей (только для авторизованных пользователей).
    """
)
async def list_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        logger.info("Запрошен список всех пользователей")
        return await crud_user.get_users(db)
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении списка пользователей: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении списка пользователей: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить пользователя по ID (только для авторизованных пользователей) ---


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Получить пользователя по ID",
    description="""
    Получение информации о пользователе по его идентификатору (только для авторизованных пользователей).
    """
)
async def get_user(
    user_id: UUID = Path(..., description="ID пользователя",
                         example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"Запрошена информация о пользователе: {user_id}")
        user = await crud_user.get_user(db, user_id)
        if not user:
            logger.warning(f"Пользователь не найден: {user_id}")
            raise HTTPException(
                status_code=404, detail="Пользователь не найден")
        return UserOut.model_validate(user)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении пользователя: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении пользователя: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Удалить пользователя (только для админов) ---


@router.delete(
    "/{user_id}",
    dependencies=[Depends(is_admin)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя",
    description="""
    Удаление пользователя по идентификатору (только для админов).
    """
)
async def delete_user(
    user_id: UUID = Path(..., description="ID пользователя",
                         example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Удаление пользователя: {user_id}")
        user = await crud_user.get_user(db, user_id)
        if not user:
            logger.warning(f"Пользователь для удаления не найден: {user_id}")
            raise HTTPException(
                status_code=404, detail="Пользователь не найден")
        await crud_user.delete_user(db, user)
        await db.commit()
        logger.info(f"Пользователь {user_id} успешно удален")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при удалении пользователя: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при удалении пользователя: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Обновить пользователя (только для админов) ---


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(is_admin)],
    summary="Частично обновить пользователя",
    description="""
    Частичное обновление информации о пользователе по идентификатору (только для админов). Можно изменить любое поле, включая username (если не занят).
    """
)
async def update_user(
    user_id: UUID = Path(..., description="ID пользователя",
                         example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    user_in: UserUpdate = ...,
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Частичное обновление пользователя: {user_id}")
        user = await crud_user.get_user(db, user_id)
        if not user:
            logger.warning(f"Пользователь для обновления не найден: {user_id}")
            raise HTTPException(
                status_code=404, detail="Пользователь не найден")
        user = await crud_user.update_user_partial(db, user, user_in)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Пользователь {user_id} успешно обновлен (PATCH)")
        return UserOut.model_validate(user)
    except ValueError as ve:
        logger.warning(f"Ошибка при смене username: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при обновлении пользователя: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при обновлении пользователя: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")
