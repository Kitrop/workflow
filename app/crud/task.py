import logging
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete, func
from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException
from app.models.task import Task, Period, Review, TaskHistory
from app.models.user import User
from app.models.project import Project
from app.schemas.task import TaskCreate, TaskOut
from app.db import AsyncSessionLocal
from app.models.task_type import TaskType

# Логгер для ошибок при работе с задачами
logger = logging.getLogger(__name__)

# --- Вспомогательные функции ---


def _get_readable_value(field: str, value: Any) -> str:
    """
    Преобразует значение поля в читаемый формат.
    """
    if value is None:
        return 'Не задано'

    # Специальная обработка для типа задачи
    if field == 'type_id':
        # value — это id типа задачи
        return f"ID типа задачи: {value}"

    # Для остальных полей просто возвращаем строковое представление
    return str(value)


def _track_field_changes(old_task_data: Dict[str, Any], new_task_data: Dict[str, Any]) -> list[Dict[str, str]]:
    """
    Сравнивает старые и новые значения полей задачи и возвращает список изменений.
    """
    changes = []

    # Словарь для сопоставления полей с их названиями
    field_names = {
        'name': 'Название',
        'type_id': 'Тип задачи',
        'issue_url': 'Ссылка на задачу',
        'issue_date': 'Дата создания',
        'assignee_id': 'Исполнитель',
        'project_id': 'Проект',
        'manager_id': 'Менеджер',
        'extra_fields': 'Дополнительные поля'
    }

    # Проверяем изменения основных полей
    for field, display_name in field_names.items():
        old_value = old_task_data.get(field)
        new_value = new_task_data.get(field)

        # Специальная обработка для extra_fields
        if field == 'extra_fields':
            if old_value != new_value:
                changes.append({
                    'field': display_name,
                    'old_value': _get_readable_value(field, old_value),
                    'new_value': _get_readable_value(field, new_value)
                })
        # Специальная обработка для дат
        elif field == 'issue_date':
            if old_value != new_value:
                changes.append({
                    'field': display_name,
                    'old_value': _get_readable_value(field, old_value),
                    'new_value': _get_readable_value(field, new_value)
                })
        # Для остальных полей
        elif old_value != new_value:
            changes.append({
                'field': display_name,
                'old_value': _get_readable_value(field, old_value),
                'new_value': _get_readable_value(field, new_value)
            })

    return changes


def _track_periods_changes(old_periods: list, new_periods: list) -> list[Dict[str, str]]:
    """
    Сравнивает старые и новые периоды и возвращает список изменений.
    """
    changes = []

    # Если количество периодов изменилось
    if len(old_periods) != len(new_periods):
        changes.append({
            'field': 'periods_count',
            'old_value': f"{len(old_periods)} периодов",
            'new_value': f"{len(new_periods)} периодов"
        })

    # Сравниваем каждый период (упрощенная логика)
    min_periods = min(len(old_periods), len(new_periods))
    for i in range(min_periods):
        old_period = old_periods[i]
        new_period = new_periods[i]

        if old_period.start != new_period.start:
            changes.append({
                'field': f'period_{i+1}_start',
                'old_value': str(old_period.start),
                'new_value': str(new_period.start)
            })

        if old_period.end != new_period.end:
            changes.append({
                'field': f'period_{i+1}_end',
                'old_value': str(old_period.end),
                'new_value': str(new_period.end)
            })

        if old_period.type != new_period.type:
            changes.append({
                'field': f'period_{i+1}_type',
                'old_value': str(old_period.type),
                'new_value': str(new_period.type)
            })

    return changes


def _track_reviews_changes(old_reviews: list, new_reviews: list) -> list[Dict[str, str]]:
    """
    Сравнивает старые и новые ревью и возвращает список изменений.
    """
    changes = []

    # Если количество ревью изменилось
    if len(old_reviews) != len(new_reviews):
        changes.append({
            'field': 'reviews_count',
            'old_value': f"{len(old_reviews)} ревью",
            'new_value': f"{len(new_reviews)} ревью"
        })

    # Сравниваем каждое ревью (упрощенная логика)
    min_reviews = min(len(old_reviews), len(new_reviews))
    for i in range(min_reviews):
        old_review = old_reviews[i]
        new_review = new_reviews[i]

        if old_review.review_date != new_review.review_date:
            changes.append({
                'field': f'review_{i+1}_date',
                'old_value': str(old_review.review_date),
                'new_value': str(new_review.review_date)
            })

    return changes

# --- CRUD-операции для задач ---


async def create_task(db: AsyncSession, task_in: TaskCreate, changed_by_id: UUID) -> Task:
    """
    Создаёт новую задачу с валидацией всех связанных сущностей и историей изменений.
    """
    try:
        # Валидация существования исполнителя
        assignee_result = await db.execute(
            select(User).where(User.id == task_in.assignee_id)
        )
        assignee = assignee_result.scalars().first()
        if not assignee:
            raise HTTPException(
                status_code=400,
                detail=f"Пользователь с ID {task_in.assignee_id} не найден"
            )

        # Валидация существования менеджера
        manager_result = await db.execute(
            select(User).where(User.id == task_in.manager_id)
        )
        manager = manager_result.scalars().first()
        if not manager:
            raise HTTPException(
                status_code=400,
                detail=f"Менеджер с ID {task_in.manager_id} не найден"
            )

        # Валидация существования проекта
        project_result = await db.execute(
            select(Project).where(Project.id == task_in.project_id)
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=400,
                detail=f"Проект с ID {task_in.project_id} не найден"
            )

        # Валидация существования типа задачи
        task_type_result = await db.execute(
            select(TaskType).where(TaskType.id == task_in.type_id)
        )
        task_type = task_type_result.scalars().first()
        if not task_type:
            raise HTTPException(
                status_code=400,
                detail=f"Тип задачи с ID {task_in.type_id} не найден"
            )

        # Создаём задачу
        task_data = task_in.model_dump(
            exclude={"periods", "reviews", "extra_fields"})
        db_task = Task(**task_data, extra_fields=task_in.extra_fields)

        db.add(db_task)
        await db.flush()
        task_id = db_task.id  # Сохраняем id до коммита

        # Добавляем периоды задачи
        if task_in.periods:
            for period_data in task_in.periods:
                # Валидация tester_id если указан
                if period_data.tester_id:
                    tester_result = await db.execute(
                        select(User).where(User.id == period_data.tester_id)
                    )
                    tester = tester_result.scalars().first()
                    if not tester:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Тестировщик с ID {period_data.tester_id} не найден"
                        )
                db.add(Period(task_id=task_id, **period_data.model_dump()))

        # Добавляем ревью задачи
        if task_in.reviews:
            for review_data in task_in.reviews:
                # Валидация reviewer_id
                reviewer_result = await db.execute(
                    select(User).where(User.id == review_data.reviewer_id)
                )
                reviewer = reviewer_result.scalars().first()
                if not reviewer:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Ревьюер с ID {review_data.reviewer_id} не найден"
                    )
                db.add(Review(task_id=task_id, **review_data.model_dump()))

        # Добавляем запись в историю изменений
        db.add(TaskHistory(
            task_id=task_id,
            changed_by_id=changed_by_id,
            field="create",
            old_value="",
            new_value=f"Создана задача '{task_in.name}'"
        ))
        await db.commit()

        # Возвращаем задачу с подгруженными связями
        result = await db.execute(
            select(Task)
            .options(
                selectinload(Task.periods),
                selectinload(Task.reviews),
                selectinload(Task.assignee),
                selectinload(Task.manager),
                selectinload(Task.project),
                selectinload(Task.task_type)
            )
            .where(Task.id == task_id)
        )
        task = result.scalars().first()
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка при создании задачи: {e}\n{traceback.format_exc()}")
        raise


async def get_task(db: AsyncSession, task_id: int) -> Optional[Task]:
    """
    Получает задачу по ID с подгруженными связями.
    """
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.periods),
            selectinload(Task.reviews),
            selectinload(Task.assignee),
            selectinload(Task.manager),
            selectinload(Task.project),
            selectinload(Task.task_type)
        )
        .where(Task.id == task_id)
    )
    return result.scalars().first()


async def get_tasks(db: AsyncSession, skip: int = 0, limit: int = 100, current_user: Optional[User] = None):
    """
    Получает список задач с пагинацией и подгруженными связями.
    Для не-админа — только задачи проектов, к которым есть доступ.
    """
    query = select(Task).options(
        selectinload(Task.periods),
        selectinload(Task.reviews),
        selectinload(Task.assignee),
        selectinload(Task.manager),
        selectinload(Task.project),
        selectinload(Task.task_type)
    )
    if current_user and current_user.role != 'admin':
        # Получаем id доступных проектов через отдельный запрос
        result = await db.execute(
            select(Project.id)
            .join(Project.users_with_access)
            .where(User.id == current_user.id)
        )
        accessible_project_ids = [row[0] for row in result.all()]
        if not accessible_project_ids:
            return []
        query = query.where(Task.project_id.in_(accessible_project_ids))
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


async def update_task(db: AsyncSession, task: Task, task_in: TaskCreate, changed_by_id: UUID) -> Task:
    """
    Обновляет задачу с полной заменой периодов и ревью, с валидацией и историей изменений.
    """
    try:
        # Валидация существования исполнителя
        assignee_result = await db.execute(
            select(User).where(User.id == task_in.assignee_id)
        )
        assignee = assignee_result.scalars().first()
        if not assignee:
            raise HTTPException(
                status_code=400,
                detail=f"Пользователь с ID {task_in.assignee_id} не найден"
            )

        # Валидация существования менеджера
        manager_result = await db.execute(
            select(User).where(User.id == task_in.manager_id)
        )
        manager = manager_result.scalars().first()
        if not manager:
            raise HTTPException(
                status_code=400,
                detail=f"Менеджер с ID {task_in.manager_id} не найден"
            )

        # Валидация существования проекта
        project_result = await db.execute(
            select(Project).where(Project.id == task_in.project_id)
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=400,
                detail=f"Проект с ID {task_in.project_id} не найден"
            )

        # Валидация существования типа задачи
        task_type_result = await db.execute(
            select(TaskType).where(TaskType.id == task_in.type_id)
        )
        task_type = task_type_result.scalars().first()
        if not task_type:
            raise HTTPException(
                status_code=400,
                detail=f"Тип задачи с ID {task_in.type_id} не найден"
            )

        # Сохраняем старые значения для отслеживания изменений
        old_task_data = {
            'name': task.name,
            'type_id': task.type_id,
            'issue_url': task.issue_url,
            'issue_date': task.issue_date,
            'assignee_id': task.assignee_id,
            'project_id': task.project_id,
            'manager_id': task.manager_id,
            'extra_fields': task.extra_fields
        }

        # Сохраняем старые периоды и ревью для сравнения
        old_periods = list(task.periods)
        old_reviews = list(task.reviews)

        # Обновляем основные поля задачи
        task.type_id = task_in.type_id
        task.name = task_in.name
        task.issue_url = task_in.issue_url
        task.issue_date = task_in.issue_date
        task.assignee_id = task_in.assignee_id
        task.project_id = task_in.project_id
        task.manager_id = task_in.manager_id
        task.extra_fields = task_in.extra_fields

        # Подготавливаем новые данные для сравнения
        new_task_data = {
            'name': task_in.name,
            'type_id': task_in.type_id,
            'issue_url': task_in.issue_url,
            'issue_date': task_in.issue_date,
            'assignee_id': task_in.assignee_id,
            'project_id': task_in.project_id,
            'manager_id': task_in.manager_id,
            'extra_fields': task_in.extra_fields
        }

        # Отслеживаем изменения полей
        field_changes = _track_field_changes(old_task_data, new_task_data)

        # Удаляем старые периоды и ревью
        await db.execute(delete(Period).where(Period.task_id == task.id))
        await db.execute(delete(Review).where(Review.task_id == task.id))

        # Добавляем новые периоды
        if task_in.periods:
            for period_data in task_in.periods:
                # Валидация tester_id если указан
                if period_data.tester_id:
                    tester_result = await db.execute(
                        select(User).where(User.id == period_data.tester_id)
                    )
                    tester = tester_result.scalars().first()
                    if not tester:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Тестировщик с ID {period_data.tester_id} не найден"
                        )
                db.add(Period(task_id=task.id, **period_data.model_dump()))

        # Добавляем новые ревью
        if task_in.reviews:
            for review_data in task_in.reviews:
                # Валидация reviewer_id
                reviewer_result = await db.execute(
                    select(User).where(User.id == review_data.reviewer_id)
                )
                reviewer = reviewer_result.scalars().first()
                if not reviewer:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Ревьюер с ID {review_data.reviewer_id} не найден"
                    )
                db.add(Review(task_id=task.id, **review_data.model_dump()))

        # Отслеживаем изменения в периодах и ревью
        periods_changes = _track_periods_changes(old_periods, task_in.periods)
        reviews_changes = _track_reviews_changes(old_reviews, task_in.reviews)

        # Группируем все изменения в одну запись
        all_changes = []

        # Добавляем изменения основных полей
        for change in field_changes:
            all_changes.append({
                'field': change['field'],
                'old_value': change['old_value'],
                'new_value': change['new_value']
            })

        # Добавляем изменения в периодах
        for change in periods_changes:
            all_changes.append({
                'field': change['field'],
                'old_value': change['old_value'],
                'new_value': change['new_value']
            })

        # Добавляем изменения в ревью
        for change in reviews_changes:
            all_changes.append({
                'field': change['field'],
                'old_value': change['old_value'],
                'new_value': change['new_value']
            })

        # Если есть изменения, создаем одну запись в истории
        if all_changes:
            import json
            db.add(TaskHistory(
                task_id=task.id,
                changed_by_id=changed_by_id,
                field="update",
                old_value="",
                new_value=json.dumps(all_changes, ensure_ascii=False, indent=2)
            ))

        await db.commit()
        await db.refresh(task)

        # Возвращаем обновленную задачу с подгруженными связями
        result = await db.execute(
            select(Task)
            .options(
                selectinload(Task.periods),
                selectinload(Task.reviews),
                selectinload(Task.assignee),
                selectinload(Task.manager),
                selectinload(Task.project),
                selectinload(Task.task_type)
            )
            .where(Task.id == task.id)
        )
        return result.scalars().first()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка при обновлении задачи: {e}\n{traceback.format_exc()}")
        raise


async def delete_task(db: AsyncSession, task: Task, changed_by_id: UUID):
    """
    Удаляет задачу и всю историю изменений по ней.
    """
    # Удаляем все связанные записи из task_history
    await db.execute(delete(TaskHistory).where(TaskHistory.task_id == task.id))
    await db.delete(task)
    await db.commit()


async def get_task_history(db: AsyncSession, task_id: int):
    """
    Получает историю изменений задачи по её ID с подгруженными связями.
    """
    result = await db.execute(
        select(TaskHistory)
        .options(selectinload(TaskHistory.changed_by))
        .where(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.changed_at.desc())
    )
    return result.scalars().all()


async def get_tasks_by_project(db: AsyncSession, project_id: int):
    """
    Получает все задачи, относящиеся к определённому проекту.
    """
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.periods),
            selectinload(Task.reviews),
            selectinload(Task.assignee),
            selectinload(Task.manager),
            selectinload(Task.project),
            selectinload(Task.task_type)
        )
        .where(Task.project_id == project_id)
    )
    return result.scalars().all()


async def get_tasks_count(db: AsyncSession, current_user: Optional[User] = None, project_id: Optional[int] = None):
    """
    Получает количество задач с учётом прав доступа пользователя.
    
    Args:
        db: Сессия базы данных
        current_user: Текущий пользователь (для проверки прав доступа)
        project_id: ID проекта (если нужно посчитать задачи только для конкретного проекта)
    
    Returns:
        dict: Словарь с количеством задач
    """
    
    # Базовый запрос для подсчёта
    if project_id:
        # Подсчёт задач для конкретного проекта
        query = select(func.count(Task.id)).where(Task.project_id == project_id)
        
        # Проверяем права доступа к проекту
        if current_user and current_user.role != 'admin':
            # Получаем id доступных проектов
            result = await db.execute(
                select(Project.id)
                .join(Project.users_with_access)
                .where(User.id == current_user.id)
            )
            accessible_project_ids = [row[0] for row in result.all()]
            
            if project_id not in accessible_project_ids:
                return {"total_count": 0, "project_count": 0}
        
        result = await db.execute(query)
        project_count = result.scalar()
        
        return {
            "total_count": project_count,
            "project_count": project_count
        }
    else:
        # Подсчёт общего количества задач
        query = select(func.count(Task.id))
        
        if current_user and current_user.role != 'admin':
            # Получаем id доступных проектов
            result = await db.execute(
                select(Project.id)
                .join(Project.users_with_access)
                .where(User.id == current_user.id)
            )
            accessible_project_ids = [row[0] for row in result.all()]
            
            if not accessible_project_ids:
                return {"total_count": 0, "project_count": None}
            
            query = query.where(Task.project_id.in_(accessible_project_ids))
        
        result = await db.execute(query)
        total_count = result.scalar()
        
        return {
            "total_count": total_count,
            "project_count": None
        }
