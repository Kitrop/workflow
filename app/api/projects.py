from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from uuid import UUID
from app.db import get_db
from app.auth import get_current_active_user, require_admin_user
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.schemas.user import UserOut
from app.crud import project as crud_project
from app.crud import user as crud_user
from app.models.project import Project
from app.models.user import User
from sqlalchemy import select, or_
import logging
import traceback

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

# --- Создать новый проект (только для админов) ---


@router.post(
    "/",
    response_model=ProjectOut,
    dependencies=[Depends(require_admin_user)],
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый проект",
    description="""
    Создание нового проекта (только для админов).
    Требуется роль администратора. Возвращает созданный проект.
    """
)
async def create_project_view(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для создания нового проекта (только для админов).
    """
    try:
        logger.info(f"Создание проекта: {project_in.name}")
        # Проверка уникальности имени проекта
        existing = await crud_project.get_project_by_name(db, project_in.name)
        if existing:
            logger.warning(
                f"Попытка создать проект с уже существующим именем: {project_in.name}")
            raise HTTPException(
                status_code=400, detail="Проект с таким именем уже существует")
        project = await crud_project.create_project(db, project_in)
        await db.commit()
        await db.refresh(project)
        logger.info(f"Проект {project.name} успешно создан")
        return ProjectOut.model_validate(project)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при создании проекта: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при создании проекта: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить список проектов ---


@router.get("/", response_model=List[ProjectOut], summary="Получить список проектов", description="""
Получение списка проектов.
- Админы видят все проекты.
- Обычные пользователи видят публичные проекты и те, к которым им выдан доступ.
""")
async def list_projects_view(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Эндпоинт для получения списка проектов с учётом прав пользователя.
    """
    try:
        logger.info(
            f"Пользователь {current_user.username} запросил список проектов")
        return await crud_project.get_user_accessible_projects(db, current_user)
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении списка проектов: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении списка проектов: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить проект по ID ---


@router.get("/{project_id}", response_model=ProjectOut, summary="Получить проект по ID", description="""
Получение информации о проекте по его идентификатору. Требуется доступ к проекту.
""")
async def get_project_view(
    project_id: int = Path(..., description="ID проекта", example=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Эндпоинт для получения информации о проекте по ID.
    """
    try:
        logger.info(
            f"Пользователь {current_user.username} запросил проект: {project_id}")
        project = await crud_project.get_project(db, project_id)
        if not project:
            logger.warning(f"Проект не найден: {project_id}")
            raise HTTPException(status_code=404, detail="Проект не найден")
        # Проверка доступа
        if not await crud_project.can_user_access_project(db, current_user, project):
            logger.warning(
                f"Пользователь {current_user.username} не имеет доступа к проекту: {project_id}")
            raise HTTPException(
                status_code=403, detail="Доступ к проекту запрещён")
        return project
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении проекта: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении проекта: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Обновить проект (только для админов) ---


@router.put(
    "/{project_id}",
    response_model=ProjectOut,
    dependencies=[Depends(require_admin_user)],
    status_code=200,
    summary="Обновить проект",
    description="""
    Обновление проекта (только для админов). Требуется роль администратора.
    """
)
async def update_project_view(
    project_id: int = Path(..., description="ID проекта", example=1),
    project_in: ProjectUpdate = ...,
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для обновления проекта (только для админов).
    """
    try:
        logger.info(f"Обновление проекта: {project_id}")
        project = await crud_project.get_project(db, project_id)
        if not project:
            logger.warning(f"Проект для обновления не найден: {project_id}")
            raise HTTPException(status_code=404, detail="Проект не найден")
        return await crud_project.update_project(db, project=project, project_in=project_in)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при обновлении проекта: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при обновлении проекта: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Удалить проект (только для админов) ---


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_user)],
    summary="Удалить проект",
    description="""
    Удаление проекта (только для админов). Требуется роль администратора.
    """
)
async def delete_project_view(project_id: int = Path(..., description="ID проекта", example=1), db: AsyncSession = Depends(get_db)):
    """
    Эндпоинт для удаления проекта (только для админов).
    """
    try:
        logger.info(f"Удаление проекта: {project_id}")
        project = await crud_project.get_project(db, project_id)
        if not project:
            logger.warning(f"Проект для удаления не найден: {project_id}")
            raise HTTPException(status_code=404, detail="Проект не найден")
        await crud_project.delete_project(db, project=project)
        logger.info(f"Проект {project_id} успешно удалён")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при удалении проекта: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при удалении проекта: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Управление доступом к проекту (только для админов) ---


@router.post(
    "/{project_id}/access",
    response_model=UserOut,
    dependencies=[Depends(require_admin_user)],
    status_code=status.HTTP_201_CREATED,
    summary="Выдать пользователю доступ к проекту",
    description="""
    Выдать пользователю доступ к проекту (только для админов). Требуется роль администратора.
    """
)
async def grant_project_access(
    project_id: int = Path(..., description="ID проекта", example=1),
    user_id: UUID = Query(..., description="ID пользователя",
                          example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для выдачи доступа пользователю к проекту (только для админов).
    """
    try:
        logger.info(
            f"Выдача доступа пользователю {user_id} к проекту {project_id}")
        project = await crud_project.get_project(db, project_id)
        if not project:
            logger.warning(
                f"Проект не найден для выдачи доступа: {project_id}")
            raise HTTPException(status_code=404, detail="Проект не найден")
        user_to_grant = await crud_user.get_user(db, user_id)
        if not user_to_grant:
            logger.warning(
                f"Пользователь не найден для выдачи доступа: {user_id}")
            raise HTTPException(
                status_code=404, detail="Пользователь не найден")
        await crud_project.grant_access_to_user(db, project=project, user=user_to_grant, admin_user=admin_user)
        await db.refresh(user_to_grant)
        logger.info(
            f"Пользователю {user_id} выдан доступ к проекту {project_id}")
        return UserOut.model_validate(user_to_grant)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при выдаче доступа: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при выдаче доступа: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.delete(
    "/{project_id}/access/{user_id}",
    dependencies=[Depends(require_admin_user)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отозвать у пользователя доступ к проекту",
    description="""
    Отозвать у пользователя доступ к проекту (только для админов). Требуется роль администратора.
    """
)
async def revoke_project_access(
    project_id: int = Path(..., description="ID проекта", example=1),
    user_id: UUID = Path(..., description="ID пользователя",
                         example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    db: AsyncSession = Depends(get_db)
):
    """
    Эндпоинт для отзыва доступа пользователя к проекту (только для админов).
    """
    try:
        logger.info(
            f"Отзыв доступа пользователя {user_id} к проекту {project_id}")
        project = await crud_project.get_project(db, project_id)
        if not project:
            logger.warning(
                f"Проект не найден для отзыва доступа: {project_id}")
            raise HTTPException(status_code=404, detail="Проект не найден")
        user_to_revoke = await crud_user.get_user(db, user_id)
        if not user_to_revoke:
            logger.warning(
                f"Пользователь не найден для отзыва доступа: {user_id}")
            raise HTTPException(
                status_code=404, detail="Пользователь не найден")
        await crud_project.revoke_access_from_user(db, project=project, user=user_to_revoke)
        logger.info(
            f"У пользователя {user_id} отозван доступ к проекту {project_id}")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при отзыве доступа: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при отзыве доступа: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить список пользователей с доступом к проекту (только для админов) ---


@router.get(
    "/{project_id}/users",
    response_model=List[UserOut],
    dependencies=[Depends(require_admin_user)],
    summary="Получить список пользователей с доступом к проекту",
    description="""
    Получить список пользователей, имеющих доступ к проекту (только для админов). Требуется роль администратора.
    """
)
async def get_project_users(project_id: int = Path(..., description="ID проекта", example=1), db: AsyncSession = Depends(get_db)):
    """
    Эндпоинт для получения списка пользователей с доступом к проекту (только для админов).
    """
    try:
        logger.info(
            f"Запрошен список пользователей с доступом к проекту: {project_id}")
        project = await crud_project.get_project(db, project_id)
        if not project:
            logger.warning(
                f"Проект не найден для получения пользователей: {project_id}")
            raise HTTPException(status_code=404, detail="Проект не найден")
        return project.users_with_access
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении пользователей проекта: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении пользователей проекта: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")
