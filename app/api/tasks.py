import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from app.db import get_db
from app.auth import get_current_user, require_project_access
from app.schemas.task import TaskCreate, TaskOut, TaskHistoryOut, TaskTypeOut, TaskCountOut
from app.models.user import User
from app.models.task import Task
from app.crud import task as crud_task
from app.models.task_type import TaskType
from sqlalchemy import select

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

# --- Создать новую задачу ---


@router.post(
    "/",
    response_model=TaskOut,
    dependencies=[Depends(get_current_user)],
    status_code=201,
    summary="Создать новую задачу",
    description="""
    Создание новой задачи. Требуется аутентификация. Возвращает созданную задачу с подробной информацией.
    """
)
async def create_task_view(task_in: TaskCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Эндпоинт для создания новой задачи.
    """
    try:
        logger.info(
            f"Пользователь {current_user.username} создаёт задачу: {task_in.name}")
        task = await crud_task.create_task(db, task_in, changed_by_id=current_user.id)
        result = TaskOut.model_validate(task)
        logger.info(f"Задача '{task_in.name}' успешно создана")
        return result
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при создании задачи: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при создании задачи: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить список задач ---


@router.get(
    "/",
    response_model=List[TaskOut],
    dependencies=[Depends(get_current_user)],
    summary="Получить список задач",
    description="""
    Получение списка задач. Требуется аутентификация. Можно использовать параметры skip и limit для пагинации.
    """
)
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(
        0, description="Сколько задач пропустить (для пагинации)", example=0),
    limit: int = Query(
        100, description="Максимальное количество задач в ответе", example=100),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"Запрошен список задач: skip={skip}, limit={limit}")
        return await crud_task.get_tasks(db, skip=skip, limit=limit, current_user=current_user)
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении списка задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении списка задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить количество задач ---


@router.get(
    "/count",
    response_model=TaskCountOut,
    dependencies=[Depends(get_current_user)],
    summary="Получить количество задач",
    description="""
    Получение количества задач для breadcrumbs и навигации. Требуется аутентификация.
    
    **Параметры:**
    - `project_id` (int, optional): ID проекта для подсчёта задач только в этом проекте
    
    **Ответ:**
    - `total_count` (int): Общее количество задач (с учётом прав доступа)
    - `project_count` (int | null): Количество задач в проекте (если указан project_id)
    
    **Использование:**
    - Для создания breadcrumbs на фронтенде
    - Для отображения общего количества задач в навигации
    - Учитывает права доступа пользователя к проектам
    """
)
async def get_tasks_count(
    project_id: Optional[int] = Query(None, description="ID проекта для подсчёта задач", example=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"Запрошено количество задач: project_id={project_id}")
        
        # Проверяем доступ к проекту, если указан
        if project_id:
            # Проверяем существование проекта
            from app.crud import project as crud_project
            project = await crud_project.get_project(db, project_id)
            if not project:
                logger.warning(f"Проект не найден: {project_id}")
                raise HTTPException(status_code=404, detail="Проект не найден")
            
            # Проверяем права доступа к проекту
            if current_user.role != 'admin':
                accessible_projects = await crud_project.get_user_accessible_projects(db, current_user)
                accessible_project_ids = [p.id for p in accessible_projects]
                if project_id not in accessible_project_ids:
                    logger.warning(f"Пользователь {current_user.username} не имеет доступа к проекту {project_id}")
                    raise HTTPException(status_code=403, detail="Нет доступа к проекту")
        
        count_data = await crud_task.get_tasks_count(db, current_user=current_user, project_id=project_id)
        
        logger.info(f"Количество задач: {count_data}")
        return TaskCountOut(**count_data)
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении количества задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении количества задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить задачу по ID ---


@router.get(
    "/{task_id}",
    response_model=TaskOut,
    dependencies=[Depends(get_current_user)],
    summary="Получить задачу по ID",
    description="""
    Получение информации о задаче по её идентификатору. Требуется аутентификация.
    """
)
async def get_task_view(
    task_id: int = Path(..., description="ID задачи", example=1),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Запрошена задача: {task_id}")
        task = await crud_task.get_task(db, task_id)
        if not task:
            logger.warning(f"Задача не найдена: {task_id}")
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return task
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении задачи: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении задачи: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Обновить задачу ---


@router.put(
    "/{task_id}",
    response_model=TaskOut,
    dependencies=[Depends(get_current_user)],
    summary="Обновить задачу",
    description="""
    Обновление задачи по идентификатору. Требуется аутентификация.
    """
)
async def update_task(
    task_id: int = Path(..., description="ID задачи", example=1),
    task_in: TaskCreate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(
            f"Пользователь {current_user.username} обновляет задачу: {task_id}")
        task = await crud_task.get_task(db, task_id)
        if not task:
            logger.warning(f"Задача для обновления не найдена: {task_id}")
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return await crud_task.update_task(db, task=task, task_in=task_in, changed_by_id=current_user.id)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при обновлении задачи: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при обновлении задачи: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Удалить задачу ---


@router.delete(
    "/{task_id}",
    dependencies=[Depends(get_current_user)],
    status_code=204,
    summary="Удалить задачу",
    description="""
    Удаление задачи по идентификатору. Требуется аутентификация.
    """
)
async def delete_task(
    task_id: int = Path(..., description="ID задачи", example=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(
            f"Пользователь {current_user.username} удаляет задачу: {task_id}")
        task = await crud_task.get_task(db, task_id)
        if not task:
            logger.warning(f"Задача для удаления не найдена: {task_id}")
            raise HTTPException(status_code=404, detail="Задача не найдена")
        await crud_task.delete_task(db, task, changed_by_id=current_user.id)
        logger.info(f"Задача {task_id} успешно удалена")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при удалении задачи: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при удалении задачи: {e}\n{traceback.format_exc()}")
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить историю изменений задачи ---


@router.get(
    "/{task_id}/history",
    response_model=List[TaskHistoryOut],
    dependencies=[Depends(get_current_user)],
    summary="Получить историю изменений задачи",
    description="""
    Получение истории изменений по задаче. Требуется аутентификация.
    """
)
async def get_task_history(
    task_id: int = Path(..., description="ID задачи", example=1),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Запрошена история изменений задачи: {task_id}")
        history_records = await crud_task.get_task_history(db, task_id)

        # Преобразуем записи в схему с дополнительной информацией
        result = []
        for record in history_records:
            # Обрабатываем JSON-структуру для обновлений
            if record.field == "update" and record.new_value:
                try:
                    import json
                    changes_data = json.loads(record.new_value)
                    # Создаем отдельную запись для каждого изменения в группе
                    for change in changes_data:
                        history_data = {
                            "id": record.id,  # Используем тот же ID для группировки
                            "task_id": record.task_id,
                            "changed_by_id": record.changed_by_id,
                            "changed_at": record.changed_at,
                            "field": change['field'],
                            "old_value": change['old_value'],
                            "new_value": change['new_value'],
                            "changed_by_username": record.changed_by.username if record.changed_by else None
                        }
                        result.append(TaskHistoryOut(**history_data))
                except (json.JSONDecodeError, KeyError):
                    # Если JSON невалидный, создаем обычную запись
                    history_data = {
                        "id": record.id,
                        "task_id": record.task_id,
                        "changed_by_id": record.changed_by_id,
                        "changed_at": record.changed_at,
                        "field": record.field,
                        "old_value": record.old_value,
                        "new_value": record.new_value,
                        "changed_by_username": record.changed_by.username if record.changed_by else None
                    }
                    result.append(TaskHistoryOut(**history_data))
            else:
                # Обычные записи (create, delete и т.д.)
                history_data = {
                    "id": record.id,
                    "task_id": record.task_id,
                    "changed_by_id": record.changed_by_id,
                    "changed_at": record.changed_at,
                    "field": record.field,
                    "old_value": record.old_value,
                    "new_value": record.new_value,
                    "changed_by_username": record.changed_by.username if record.changed_by else None
                }
                result.append(TaskHistoryOut(**history_data))

        return result
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении истории задачи: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении истории задачи: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить задачи по проекту ---


@router.get(
    "/by_project/{project_id}",
    response_model=List[TaskOut],
    dependencies=[Depends(get_current_user), Depends(require_project_access)],
    summary="Получить задачи по проекту",
    description="""
    Получение всех задач, относящихся к определённому проекту. Требуется аутентификация.
    """
)
async def get_tasks_by_project(
    project_id: int = Path(..., description="ID проекта", example=1),
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Запрошены задачи по проекту: {project_id}")
        tasks = await crud_task.get_tasks_by_project(db, project_id)
        logger.info(f"Найдено задач по проекту {project_id}: {len(tasks)}")
        return [TaskOut.model_validate(task) for task in tasks]
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении задач по проекту: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении задач по проекту: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить количество задач по проекту ---


@router.get(
    "/by_project/{project_id}/count",
    response_model=TaskCountOut,
    dependencies=[Depends(get_current_user), Depends(require_project_access)],
    summary="Получить количество задач по проекту",
    description="""
    Получение количества задач для конкретного проекта. Требуется аутентификация и доступ к проекту.
    
    **Ответ:**
    - `total_count` (int): Количество задач в проекте
    - `project_count` (int): Количество задач в проекте (то же значение)
    
    **Использование:**
    - Для создания breadcrumbs на странице проекта
    - Для отображения количества задач в навигации проекта
    """
)
async def get_tasks_count_by_project(
    project_id: int = Path(..., description="ID проекта", example=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"Запрошено количество задач по проекту: {project_id}")
        
        count_data = await crud_task.get_tasks_count(db, current_user=current_user, project_id=project_id)
        
        logger.info(f"Количество задач в проекте {project_id}: {count_data}")
        return TaskCountOut(**count_data)
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении количества задач по проекту: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении количества задач по проекту: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")

# --- Получить список всех типов задач (справочник) ---


@router.get(
    "/task_types",
    response_model=List[TaskTypeOut],
    summary="Получить список всех типов задач (справочник)",
    description="""
    Возвращает полный справочник типов задач.
    
    **Ответ:**
    - Список объектов типа задачи:
      - `id` (int): ID типа задачи
      - `name` (str): Код типа задачи (machine name, например, "development")
      - `display_name` (str): Человекочитаемое название (например, "Разработка")
      - `description` (str | null): Описание типа задачи (если есть)
    
    **Edge-cases:**
    - Если справочник пуст — возвращается пустой список.
    - Для фронта рекомендуется использовать поле `id` для выбора, а `display_name` для отображения.
    
    **Использование:**
    - Для выпадающих списков, фильтров, отображения типа задачи в задачах и отчётах.
    - Не требует аутентификации.
    """
)
async def get_task_types(db: AsyncSession = Depends(get_db)) -> List[TaskTypeOut]:
    try:
        result = await db.execute(select(TaskType))
        types = result.scalars().all()
        return [TaskTypeOut(
            id=t.id,
            name=t.name,
            display_name=t.display_name,
            description=t.description
        ) for t in types]
    except Exception as e:
        logger.error(
            f"Ошибка при получении справочника типов задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Ошибка получения справочника типов задач")
