from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from uuid import UUID
from app.db import get_db
from app.auth import get_current_user
from app.schemas.user import UserOut
from app.schemas.project import ProjectOut
from app.models.user import User
from app.models.project import Project
import logging
import traceback
from app.crud import project as crud_project

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

# --- Автодополнение пользователей ---


@router.get(
    "/users",
    response_model=List[UserOut],
    dependencies=[Depends(get_current_user)],
    summary="Автодополнение пользователей по имени или username",
    description="""
    Возвращает список пользователей, подходящих под строку поиска (по username или ФИО). Требуется аутентификация.
    """
)
async def autocomplete_users(
    query: str = Query(...,
                       description="Строка поиска по username или ФИО", example="Иван"),
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для автодополнения пользователей по username или ФИО.
    """
    try:
        logger.info(f"Автодополнение пользователей, query='{query}'")
        result = await db.execute(
            select(User).where(User.username.ilike(
                f"%{query}%") | User.full_name.ilike(f"%{query}%"))
        )
        users = result.scalars().all()
        logger.info(f"Найдено пользователей: {len(users)}")
        return users
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при автодополнении пользователей: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при автодополнении пользователей: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Автодополнение проектов ---


@router.get(
    "/projects",
    response_model=List[ProjectOut],
    dependencies=[Depends(get_current_user)],
    summary="Автодополнение проектов по названию",
    description="""
    Возвращает список проектов, подходящих под строку поиска по названию. 
    Показывает только проекты, к которым у пользователя есть доступ.
    Требуется аутентификация.
    """
)
async def autocomplete_projects(
    query: str = Query(...,
                       description="Строка поиска по названию проекта", example="CRM"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Эндпоинт для автодополнения проектов по названию с учетом прав доступа.
    """
    try:
        logger.info(
            f"Автодополнение проектов, query='{query}', пользователь: {current_user.username}")

        # Получаем проекты с учетом прав доступа
        accessible_projects = await crud_project.get_user_accessible_projects(db, current_user)

        # Фильтруем проекты по поисковому запросу
        filtered_projects = [
            project for project in accessible_projects
            if query.lower() in project.name.lower()
        ]

        logger.info(f"Найдено доступных проектов: {len(filtered_projects)}")
        return filtered_projects
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при автодополнении проектов: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при автодополнении проектов: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Автодополнение (админов) ---


@router.get(
    "/managers",
    response_model=List[UserOut],
    dependencies=[Depends(get_current_user)],
    summary="Автодополнение менеджеров (админов) по имени или username",
    description="""
    Возвращает список пользователей с ролью 'admin', подходящих под строку поиска (по username или ФИО). Требуется аутентификация.
    """
)
async def autocomplete_managers(
    query: str = Query(...,
                       description="Строка поиска по username или ФИО", example="Петр"),
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для автодополнения менеджеров (админов) по username или ФИО.
    """
    try:
        logger.info(f"Автодополнение менеджеров, query='{query}'")
        result = await db.execute(
            select(User).where((User.role == "admin") & (User.username.ilike(
                f"%{query}%") | User.full_name.ilike(f"%{query}%")))
        )
        managers = result.scalars().all()
        logger.info(f"Найдено менеджеров: {len(managers)}")
        return managers
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при автодополнении менеджеров: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при автодополнении менеджеров: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")
