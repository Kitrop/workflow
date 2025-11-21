from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError
from datetime import date
from typing import List
from uuid import UUID
from collections import defaultdict
from app.db import get_db
from app.auth import get_current_user, require_admin_user
from app.models.task import Task, Review, Period
from app.models.project import Project
from app.models.user import User
from app.models.task_type import TaskType
import logging
import traceback
import pandas as pd

from app.schemas.user import UserOut

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


def normalize(values: dict[str, float]) -> dict[str, float]:
    """
    Нормализует значения по формуле (x-min)/(max-min). Если все значения одинаковы, возвращает 1.0 для всех.
    """
    if not values:
        return {}
    min_v = min(values.values())
    max_v = max(values.values())
    if max_v == min_v:
        return {k: 1.0 for k in values}
    return {k: (v - min_v) / (max_v - min_v) for k, v in values.items()}


# --- ХЕЛПЕР ДЛЯ ОБРАБОТКИ ОШИБОК ---
def handle_report_exception(e: Exception, context: str = ""):
    logger.error(f"Ошибка в отчёте {context}: {e}\n{traceback.format_exc()}")
    if isinstance(e, SQLAlchemyError):
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/gantt",
    summary="Получить Gantt-отчет по задачам пользователя",
    description="""
    Эндпоинт возвращает список задач пользователя для построения диаграммы Ганта за указанный период.

    **Параметры:**
    - `user_id` (UUID): ID пользователя, для которого строится отчет.
    - `date_from` (date): Начальная дата периода (в формате YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (в формате YYYY-MM-DD).

    **Ответ:**
    - Список задач с полями: `task_id`, `name`, `issue_date`, `periods` (список периодов с датами), `user` (id и ФИО).
    - Если задач нет, возвращается пустой список.

    **Использование:**
    - Для визуализации загрузки пользователя по задачам на фронте (Gantt chart).
    - Требуется роль moderator или admin.
    """
)
async def report_gantt(
    user_id: UUID = Query(..., description="ID пользователя",
                          example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для получения Gantt-отчета по задачам пользователя.
    """
    try:
        logger.info(
            f"Gantt-отчет: user_id={user_id}, date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task).where(
                Task.assignee_id == user_id,
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            ).options(selectinload(Task.periods))
        )
        tasks = result.scalars().all()
        if not tasks:
            logger.info(f"Gantt-отчет: задач не найдено для user_id={user_id}")
            return []
        logger.info(f"Gantt-отчет: найдено задач: {len(tasks)}")
        return [
            {
                "task_id": t.id,
                "name": t.name,
                "issue_date": t.issue_date,
                "periods": [{"start": p.start, "end": p.end} for p in t.periods],
                "user": {"id": t.assignee.id if t.assignee else None, "full_name": t.assignee.full_name if t.assignee else None}
            }
            for t in tasks
        ]
    except Exception as e:
        handle_report_exception(e, context="Gantt")


@router.get(
    "/pie/tasks_by_type",
    summary="Получить pie-отчет по задачам по типу",
    description="""
    Эндпоинт возвращает распределение задач по типам за указанный период для построения pie-диаграммы.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (человекочитаемое название типа задачи, из справочника TaskType.display_name), `value` (количество задач).
    - Если задач нет, возвращается пустой список.
    - Возможные значения label: все значения поля display_name из справочника типов задач (например, "Разработка", "Исследование", "Управление").

    **Edge-cases:**
    - Если тип задачи был удалён из справочника, такие задачи не попадут в отчёт.
    - Если нет задач за период — возвращается пустой список.

    **Использование:**
    - Для отображения структуры задач по типам (pie chart) на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_tasks_by_type(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по задачам по типу.
    """
    try:
        logger.info(
            f"Pie-отчет по типу задач: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(TaskType.display_name, func.count(Task.id))
            .join(Task, Task.type_id == TaskType.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
            .group_by(TaskType.display_name)
        )
        data = [{"label": row[0], "value": row[1]} for row in result.all()]
        if not data:
            logger.info(
                "Pie-отчет по типу задач: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по типу задач: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/tasks_by_type")


@router.get(
    "/pie/projects_by_type",
    summary="Получить pie-отчет по проектам и типам задач",
    description="""
    Эндпоинт возвращает распределение задач по типам в разрезе проектов за указанный период.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Словарь: ключ — название проекта, значение — список объектов с `label` (человекочитаемое название типа задачи, из справочника TaskType.display_name) и `value` (количество).
    - Если задач нет, возвращается пустой словарь.
    - Возможные значения label: все значения поля display_name из справочника типов задач.

    **Edge-cases:**
    - Если проект не содержит задач за период — ключа не будет в ответе.
    - Если тип задачи был удалён из справочника, такие задачи не попадут в отчёт.

    **Использование:**
    - Для построения pie-диаграмм по проектам и типам задач на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_projects_by_type(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по проектам и типам задач.
    """
    try:
        logger.info(
            f"Pie-отчет по проектам и типам задач: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Project.name, TaskType.display_name, func.count(Task.id))
            .join(Task, Task.project_id == Project.id)
            .join(TaskType, Task.type_id == TaskType.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
            .group_by(Project.name, TaskType.display_name)
        )
        data = defaultdict(list)
        for project, ttype, count in result.all():
            data[project].append({"label": ttype, "value": count})
        if not data:
            logger.info(
                "Pie-отчет по проектам и типам задач: нет данных для выбранного периода")
            return {}
        logger.info(f"Pie-отчет по проектам и типам задач: {dict(data)}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/projects_by_type")


@router.get(
    "/pie/reviewers",
    summary="Получить pie-отчет по ревьюерам",
    description="""
    Эндпоинт возвращает распределение ревью по пользователям за указанный период для построения pie-диаграммы.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (ФИО ревьюера), `value` (количество ревью).
    - Если данных нет, возвращается пустой список.

    **Использование:**
    - Для визуализации активности ревьюеров (pie chart) на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_reviewers(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по ревьюерам.
    """
    try:
        logger.info(
            f"Pie-отчет по ревьюерам: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(User.full_name, func.count(Review.id)).join(Review, Review.reviewer_id == User.id).where(
                Review.review_date >= date_from,
                Review.review_date <= date_to
            ).group_by(User.full_name)
        )
        data = [{"label": row[0], "value": row[1]} for row in result.all()]
        if not data:
            logger.info(
                "Pie-отчет по ревьюерам: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по ревьюерам: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/reviewers")


@router.get(
    "/pie/testers",
    summary="Получить pie-отчет по тестировщикам",
    description="""
    Эндпоинт возвращает распределение тестовых периодов по тестировщикам за указанный период.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (ФИО тестировщика), `value` (количество тестовых периодов).
    - Если данных нет, возвращается пустой список.

    **Использование:**
    - Для построения pie-диаграммы по тестировщикам на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_testers(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по тестировщикам.
    """
    try:
        logger.info(
            f"Pie-отчет по тестировщикам: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(User.full_name, func.count(Period.id))
            .join(Period, Period.tester_id == User.id)
            .where(
                Period.type == 'test',
                Period.start >= date_from,
                Period.end <= date_to
            )
            .group_by(User.full_name)
        )
        data = [{"label": row[0], "value": row[1]} for row in result.all()]
        if not data:
            logger.info(
                "Pie-отчет по тестировщикам: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по тестировщикам: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/testers")


@router.get(
    "/pie/sp_by_project",
    summary="Получить pie-отчет по story points по проектам",
    description="""
    Эндпоинт возвращает распределение story points по проектам за указанный период.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (название проекта), `value` (сумма story points).
    - Если данных нет, возвращается пустой список.

    **Использование:**
    - Для построения pie-диаграмм story points по проектам на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_sp_by_project(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по story points по проектам.
    """
    try:
        logger.info(
            f"Pie-отчет по story points по проектам: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, Project.name)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        project_sp = defaultdict(float)
        for task, project_name in result.all():
            extra_fields = task.extra_fields or {}
            sp = extra_fields.get('sp')
            if sp is not None and isinstance(sp, (int, float)):
                project_sp[project_name] += float(sp)
        data = [{"label": project, "value": sp}
                for project, sp in project_sp.items()]
        if not data:
            logger.info(
                "Pie-отчет по story points по проектам: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по story points по проектам: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/sp_by_project")


@router.get(
    "/pie/loc_by_user",
    summary="Получить pie-отчет по количеству строк кода по пользователям",
    description="""
    Эндпоинт возвращает распределение количества строк кода по пользователям за указанный период.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (ФИО пользователя), `value` (количество строк кода).
    - Если данных нет, возвращается пустой список.

    **Использование:**
    - Для построения pie-диаграммы по LOC на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_loc_by_user(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по количеству строк кода по пользователям.
    """
    try:
        logger.info(
            f"Pie-отчет по строкам кода по пользователям: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, User.full_name)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_loc = defaultdict(int)
        for task, user_name in result.all():
            extra_fields = task.extra_fields or {}
            loc_plus = extra_fields.get('loc(+)', 0)
            loc_minus = extra_fields.get('loc(-)', 0)
            total_loc = 0
            if isinstance(loc_plus, (int, float)):
                total_loc += loc_plus
            if isinstance(loc_minus, (int, float)):
                total_loc += loc_minus
            if total_loc > 0:
                user_loc[user_name] += int(total_loc)
        data = [{"label": user, "value": loc}
                for user, loc in user_loc.items()]
        if not data:
            logger.info(
                "Pie-отчет по строкам кода по пользователям: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по строкам кода по пользователям: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/loc_by_user")


@router.get(
    "/pie/sp_by_user",
    summary="Получить pie-отчет по story points по пользователям",
    description="""
    Эндпоинт возвращает распределение story points по пользователям за указанный период.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (ФИО пользователя), `value` (сумма story points).
    - Если данных нет, возвращается пустой список.

    **Использование:**
    - Для построения pie-диаграммы story points по пользователям на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_sp_by_user(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по story points по пользователям.
    """
    try:
        logger.info(
            f"Pie-отчет по story points по пользователям: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, User.full_name)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_sp = defaultdict(float)
        for task, user_name in result.all():
            extra_fields = task.extra_fields or {}
            sp = extra_fields.get('sp')
            if sp is not None and isinstance(sp, (int, float)):
                user_sp[user_name] += float(sp)
        data = [{"label": user, "value": sp} for user, sp in user_sp.items()]
        if not data:
            logger.info(
                "Pie-отчет по story points по пользователям: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по story points по пользователям: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/sp_by_user")


@router.get(
    "/pie/tasks_by_user",
    summary="Получить pie-отчет по задачам по пользователям",
    description="""
    Эндпоинт возвращает распределение задач по пользователям за указанный период.

    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).

    **Ответ:**
    - Список объектов: `label` (ФИО пользователя), `value` (количество задач).
    - Если данных нет, возвращается пустой список.

    **Использование:**
    - Для построения pie-диаграммы задач по пользователям на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_pie_tasks_by_user(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для pie-отчета по задачам по пользователям.
    """
    try:
        logger.info(
            f"Pie-отчет по задачам по пользователям: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(User.full_name, func.count(Task.id)).join(Task, Task.assignee_id == User.id).where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            ).group_by(User.full_name)
        )
        data = [{"label": row[0], "value": row[1]} for row in result.all()]
        if not data:
            logger.info(
                "Pie-отчет по задачам по пользователям: нет данных для выбранного периода")
            return []
        logger.info(f"Pie-отчет по задачам по пользователям: {data}")
        return data
    except Exception as e:
        handle_report_exception(e, context="pie/tasks_by_user")


@router.get(
    "/aggregate/by_user",
    summary="Получить агрегированный отчет по исполнителям (старая версия)",
    description="""
    СТАРАЯ ВЕРСИЯ! Эндпоинт возвращает агрегированный отчет по исполнителям за указанный период (логика на pandas, результат тот же).
    """
)
async def report_aggregate_by_user(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        result = await db.execute(
            select(Task, User.full_name, Project.name)
            .join(User, Task.assignee_id == User.id)
            .join(Project, Task.project_id == Project.id)
            .where(Task.issue_date >= date_from, Task.issue_date <= date_to)
        )

        # 1. Собираем строки
        records = []
        for task, user_name, project_name in result.all():
            extra = task.extra_fields or {}
            loc_plus = extra.get("loc(+)", 0)
            loc_minus = extra.get("loc(-)", 0)
            total_loc = 0
            if isinstance(loc_plus, (int, float)):
                total_loc += loc_plus
            if isinstance(loc_minus, (int, float)):
                total_loc += loc_minus
            sp = extra.get("sp", 0)
            if not isinstance(sp, (int, float)):
                sp = 0
            records.append({
                "user": user_name,
                "project": project_name,
                "task_id": task.id,
                "loc": total_loc,
                "sp": sp
            })

        if not records:
            logger.info("[PANDAS] Нет задач в указанном диапазоне.")
            return []

        # 2. DataFrame
        import pandas as pd
        df = pd.DataFrame(records)

        # 3. Подсчёты
        task_counts = df.groupby("user")["task_id"].count()
        project_tasks = df.groupby(["user", "project"]).size().unstack(fill_value=0)
        loc_sums = df.groupby("user")["loc"].sum()
        sp_sums = df.groupby("user")["sp"].sum()
        sp_nonzero_counts = df[df["sp"] != 0].groupby("user")["sp"].count()

        users = set(task_counts.index) | set(loc_sums.index) | set(sp_sums.index)
        user_sp_avg = {
            u: sp_sums.get(u, 0.0) / (sp_nonzero_counts.get(u, 1))
            for u in users
        }

        # 4. Вычисление min/max
        max_sp_sum = max((v for v in sp_sums.values if v > 0), default=0)
        min_sp_sum = min((v for v in sp_sums.values if v > 0), default=0)

        task_values = task_counts.values
        max_tasks = max(task_values, default=1)
        min_tasks = min(task_values, default=0)

        sp_avg_values = [v for v in user_sp_avg.values() if v > 0]
        max_sp_avg = max(sp_avg_values, default=0)
        min_sp_avg = min(sp_avg_values, default=0)

        loc_values = loc_sums.values
        loc_values = [v for v in loc_values if v > 0]
        max_loc = max(loc_values, default=0)
        min_loc = min(loc_values, default=0)

        # 5. Формирование финальных строк
        filtered_data = []
        for user in users:
            user_tasks = task_counts.get(user, 0)
            user_loc = loc_sums.get(user, 0)
            user_sp_sum = sp_sums.get(user, 0.0)
            user_sp_avg_val = user_sp_avg.get(user, 0.0)

            if user_loc == 0 and user_sp_sum == 0:
                continue

            ntasks = (user_tasks - min_tasks) / \
                (max_tasks - min_tasks) if max_tasks != min_tasks else 1.0
            nloc = (user_loc - min_loc) / \
                (max_loc - min_loc) if max_loc != min_loc else 1.0
            nsp_sum = (user_sp_sum - min_sp_sum) / \
                (max_sp_sum - min_sp_sum) if max_sp_sum != min_sp_sum else 1.0
            nsp_avg = (user_sp_avg_val - min_sp_avg) / \
                (max_sp_avg - min_sp_avg) if max_sp_avg != min_sp_avg else 1.0

            agg = 0.25 * (ntasks + nloc + nsp_sum + nsp_avg)

            filtered_data.append({
                "user": user,
                "aggregate": round(agg, 9),
                "tasks": int(user_tasks),
                "project_tasks": project_tasks.loc[user].to_dict()
                    if user in project_tasks.index else {},
                "loc": int(user_loc),
                "sp_sum": float(user_sp_sum),
                "sp_avg": round(user_sp_avg_val, 9),
                "normalize_tasks": round(ntasks, 9),
                "normalize_loc": round(nloc, 9),
                "normalize_sp_sum": round(nsp_sum, 9),
                "normalize_sp_avg": round(nsp_avg, 9),
            })

        filtered_data.sort(key=lambda x: x["aggregate"], reverse=True)
        logger.info(f"[PANDAS] filtered_data: {filtered_data}")
        return filtered_data

    except Exception as e:
        handle_report_exception(e, context="aggregate/by_user_old")

@router.get(
    "/sp_avg/by_user",
    summary="Получить среднее значение story points по пользователям",
    description="""
    Эндпоинт возвращает среднее значение story points (sp_avg) по каждому пользователю за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - Список объектов: `user` (ФИО пользователя), `sp_avg` (среднее значение story points).
    - Если данных нет, возвращается пустой список.
    
    **Использование:**
    - Для построения bar-диаграммы среднего story points по пользователям на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_sp_avg_by_user(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для получения sp_avg по пользователям.
    """
    try:
        result = await db.execute(
            select(Task, User.full_name)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_sp_sum = defaultdict(float)
        user_sp_count = defaultdict(int)
        for task, user_name in result.all():
            extra_fields = task.extra_fields or {}
            sp = extra_fields.get('sp')
            if isinstance(sp, (int, float)):
                user_sp_sum[user_name] += sp
                if sp != 0:
                    user_sp_count[user_name] += 1
        data = [
            {"user": user, "sp_avg": user_sp_sum[user] / user_sp_count[user]}
            for user in user_sp_sum
            if user_sp_count[user] > 0
        ]
        if not data:
            logger.info(
                "sp_avg по пользователям: нет данных для выбранного периода")
            return []
        return data
    except Exception as e:
        handle_report_exception(e, context="sp_avg/by_user")


@router.get(
    "/loc/by_user",
    summary="Получить количество строк кода по пользователям",
    description="""
    Эндпоинт возвращает количество строк кода (loc) по каждому пользователю за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - Список объектов: `user` (ФИО пользователя), `loc` (количество строк кода).
    - Если данных нет, возвращается пустой список.
    
    **Использование:**
    - Для построения bar-диаграммы по LOC на фронте.
    - Требуется роль moderator или admin.
    """
)
async def report_loc_by_user(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """
    Эндпоинт для получения loc по пользователям.
    """
    try:
        result = await db.execute(
            select(Task, User.full_name)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_loc = defaultdict(int)
        for task, user_name in result.all():
            extra_fields = task.extra_fields or {}
            loc_plus = extra_fields.get('loc(+)', 0)
            loc_minus = extra_fields.get('loc(-)', 0)
            total_loc = 0
            if isinstance(loc_plus, (int, float)):
                total_loc += loc_plus
            if isinstance(loc_minus, (int, float)):
                total_loc += loc_minus
            if total_loc > 0:
                user_loc[user_name] += int(total_loc)
        data = [
            {"user": user, "loc": loc}
            for user, loc in user_loc.items() if loc > 0
        ]
        if not data:
            logger.info(
                "loc по пользователям: нет данных для выбранного периода")
            return []
        return data
    except Exception as e:
        handle_report_exception(e, context="loc/by_user")
