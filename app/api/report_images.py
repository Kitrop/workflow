from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
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
from app.crud.project import get_project
from app.models.task_type import TaskType
import logging
import traceback
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import numpy as np
from matplotlib.dates import DayLocator, DateFormatter
import matplotlib.dates as mdates
from datetime import timedelta
import pandas as pd
import matplotlib.patheffects

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Настройка matplotlib для работы без GUI
plt.switch_backend('Agg')
sns.set_style("whitegrid")

router = APIRouter()

# --- Маппинги для человекочитаемых подписей ---
PERIOD_TYPE_LABELS = {
    'work': 'Работа',
    'test': 'Тест',
}


def _get_readable_label(field: str, value):
    if field == 'type':
        # value — это TaskType.display_name или TaskType.code
        return value if value else 'Неизвестно'
    if field == 'period_type':
        return PERIOD_TYPE_LABELS.get(str(value), str(value))
    return str(value)


def _create_pie_chart(data: List[dict], title: str, figsize: tuple = (10, 8), colors: list = None) -> bytes:
    """
    Создает pie-диаграмму из данных.
    """
    # Фильтруем элементы с value == 0
    data = [item for item in data if item.get('value', 0) > 0]
    if not data:
        # Создаем пустую диаграмму
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'Нет данных', ha='center',
                va='center', transform=ax.transAxes, fontsize=14, fontname="Times New Roman")
        ax.set_title(title, fontsize=16, fontweight='bold',
                     fontname="Times New Roman")
        ax.axis('off')
    else:
        # --- Сортировка по убыванию значения ---
        data = sorted(data, key=lambda x: x['value'], reverse=True)
        # --- Ограничение длины подписи ---
        def short_label(label, max_len=30):
            if len(label) <= max_len:
                return label
            return label[:max_len-3] + '...'
        labels = [short_label(item['label']) for item in data]
        values = [item['value'] for item in data]
        # --- Цвета ---
        if colors is None:
            if all('color' in item for item in data):
                colors = [item['color'] or '#1f77b4' for item in data]
            else:
                colors = sns.color_palette("husl", len(labels))
        # --- Автоматическое уменьшение размера шрифта ---
        if len(labels) > 8:
            label_fontsize = 9
        else:
            label_fontsize = 12
        fig, ax = plt.subplots(figsize=figsize)
        # --- Подписи только в легенде для всех случаев ---
        wedges, texts, autotexts = ax.pie(
            values, labels=None, autopct='%1.1f%%', colors=colors, startangle=90)
        # Легенда: подпись, абсолютное значение, процент
        total = sum(values)
        legend_labels = [
            f'{label} ({value/total*100:.1f}%)'
            for label, value in zip(labels, values)
        ]
        ax.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1, 0.5), fontsize=label_fontsize)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontname("Times New Roman")
            autotext.set_fontsize(label_fontsize)
            autotext.set_path_effects([matplotlib.patheffects.withStroke(linewidth=1.5, foreground='black')])
        ax.set_title(title, fontsize=16, fontweight='bold',
                     pad=20, fontname="Times New Roman")
    # Сохраняем в байты
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


def _create_bar_chart(data: List[dict], title: str, figsize: tuple = (12, 8), colors: list = None) -> bytes:
    """
    Создает bar-диаграмму из данных.
    """
    if not data:
        # Создаем пустую диаграмму
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'Нет данных', ha='center',
                va='center', transform=ax.transAxes, fontsize=14, fontname="Times New Roman")
        ax.set_title(title, fontsize=16, fontweight='bold',
                     fontname="Times New Roman")
        ax.axis('off')
    else:
        labels = [item['label'] for item in data]
        values = [item['value'] for item in data]
        if colors is None:
            colors = sns.color_palette("viridis", len(labels))
        fig, ax = plt.subplots(figsize=figsize)
        bars = ax.bar(labels, values, color=colors)
        # Добавляем значения на столбцы
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                    f'{value}', ha='center', va='bottom', fontweight='bold', fontname="Times New Roman")
        ax.set_title(title, fontsize=16, fontweight='bold',
                     pad=20, fontname="Times New Roman")
        ax.set_xlabel('Пользователи', fontsize=12, fontname="Times New Roman")
        ax.set_ylabel('Среднее количество Story Points',
                      fontsize=12, fontname="Times New Roman")
        plt.xticks(rotation=45, ha='right', fontname="Times New Roman")
        plt.yticks(fontname="Times New Roman")
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


def _wrap_label(label: str, max_len=30):
    if len(label) <= max_len:
        return label
    words = label.split()
    lines = []
    current = ""
    for word in words:
        if len(current + ' ' + word) <= max_len:
            current += ' ' + word if current else word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


# PROJECT_COLORS = {
#     "BigData": "#1f77b4",
#     "MTUCI jobs": "#ff7f0e",
#     "MedForce rework": "#2ca02c",
# }
BAR_COLOR = "#1f77b4"  # единый цвет для всех баров

START_DATE = None  # будет определяться по данным
END_DATE = None


def _create_gantt_chart(tasks_data: list[dict], title: str, figsize: tuple = (16, 10)) -> bytes:
    """
    Создает Gantt-диаграмму из списка задач (tasks_data)
    """
    if not tasks_data:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, 'Нет данных', ha='center',
                va='center', transform=ax.transAxes, fontsize=14, fontname="Times New Roman")
        ax.set_title(title, fontsize=16, fontweight='bold',
                     fontname="Times New Roman")
        ax.axis('off')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    # --- Подготовка данных: каждая строка = отдельный период, сортировка по start ---
    period_rows = []
    no_period_rows = []
    for task in tasks_data:
        name = task.get('name', '')
        project = task.get('project', None)
        issue_date = task.get('issue_date', None)
        periods = task.get('periods', [])
        color = task.get('color', '#1f77b4')
        if not periods:
            no_period_rows.append({
                'Задача': name,
                'Проект': project,
                'Выдана': issue_date,
                'В работе начало': None,
                'В работе конец': None,
                'color': color
            })
        else:
            for period in periods:
                start = period.get('start')
                end = period.get('end')
                period_rows.append({
                    'Задача': name,
                    'Проект': project,
                    'Выдана': issue_date,
                    'В работе начало': start,
                    'В работе конец': end,
                    'color': color
                })
    # Сортировка всех периодов по start, None в конец
    period_rows = sorted(period_rows, key=lambda x: (
        x['В работе начало'] is None, x['В работе начало']))
    # Объединяем: сначала периоды, потом задачи без periods
    rows = period_rows + no_period_rows
    df = pd.DataFrame(rows)
    # Сортировка по дате взятия задачи в работу
    df = df.sort_values(by="В работе начало",
                        ascending=True, na_position="last")
    # --- Определение диапазона дат ---
    global START_DATE, END_DATE
    all_starts = pd.to_datetime(
        df['В работе начало'].dropna(), errors='coerce')
    all_ends = pd.to_datetime(df['В работе конец'].dropna(), errors='coerce')
    if not all_starts.empty and not all_ends.empty:
        START_DATE = all_starts.min() - timedelta(days=2)
        END_DATE = all_ends.max() + timedelta(days=2)
    else:
        START_DATE = pd.to_datetime('today')
        END_DATE = START_DATE + timedelta(days=30)
    # --- Построение ---
    labels = [_wrap_label(t) for t in df['Задача']]
    y_positions = range(len(labels))
    fig_height = max(6, 0.7 * len(labels))
    fontsize = 12 if len(labels) <= 25 else 10
    fig, ax = plt.subplots(figsize=(12, fig_height))
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontfamily="Times New Roman", fontsize=fontsize)
    for y in y_positions:
        ax.axhline(y + 0.5, color="#DDDDDD", linewidth=0.8, zorder=1)
    current = START_DATE
    while current <= END_DATE:
        ax.axvline(current, color="#EEEEEE", linewidth=0.6, zorder=0)
        current += timedelta(days=1)
    ax.set_xlim(START_DATE, END_DATE)
    ax.xaxis.set_major_locator(
        mdates.AutoDateLocator(minticks=10, maxticks=30))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    ax.tick_params(axis="x", rotation=60, labelsize=10)
    for label in ax.get_xticklabels():
        label.set_fontname("Times New Roman")
    ax.xaxis.set_minor_locator(mdates.DayLocator())
    ax.set_ylim(-0.5, len(labels) - 0.5)
    ax.invert_yaxis()
    for i, row in df.iterrows():
        start = row['В работе начало']
        end = row['В работе конец']
        issued_date = row['Выдана']
        color = row.get('color', '#1f77b4')
        if pd.notna(start) and pd.notna(end):
            duration = (end - start).days + 1
            ax.barh(i, duration, left=start, height=0.6, align="center",
                    color=color, edgecolor='black', zorder=3)
        if pd.notna(issued_date):
            ax.plot(issued_date, i, marker='o',
                    markersize=6, color='black', zorder=4)
    ax.set_title(title, pad=16, fontfamily="Times New Roman", fontsize=14)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


def _image_to_base64(image_bytes: bytes) -> str:
    """
    Конвертирует изображение в base64 строку.
    """
    return base64.b64encode(image_bytes).decode('utf-8')


@router.get(
    "/gantt",
    summary="Получить Gantt-диаграмму по задачам пользователя",
    description="""
    Эндпоинт возвращает PNG-изображение диаграммы Ганта по задачам пользователя за указанный период.
    
    **Параметры:**
    - `user_id` (UUID): ID пользователя, для которого строится отчет.
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с Gantt-диаграммой.
    - Если задач нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для визуализации загрузки пользователя по задачам на фронте (Gantt chart).
    - Требуется роль moderator или admin.
    """
)
async def get_gantt_image(
    user_id: UUID = Query(..., description="ID пользователя",
                          example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a"),
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Gantt-диаграмма: user_id={user_id}, date_from={date_from}, date_to={date_to}")
        # Получаем задачи пользователя с периодами и цветом проекта
        result = await db.execute(
            select(Task, Project.name, Project.color)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.assignee_id == user_id,
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            ).options(selectinload(Task.periods), selectinload(Task.assignee))
        )
        tasks = result.all()
        logger.info(f"Найдено задач: {len(tasks)} для user_id={user_id}")
        # Получаем имя пользователя напрямую по user_id
        user_obj = await db.get(User, user_id)
        user_name = user_obj.full_name if user_obj and user_obj.full_name else "Неизвестный пользователь"
        # Преобразуем в формат для Gantt-диаграммы
        tasks_data = []
        for task, project_name, color in tasks:
            task_data = {
                "task_id": task.id,
                "name": task.name,
                "issue_date": task.issue_date,
                "periods": [{"start": p.start, "end": p.end, "type": p.type} for p in task.periods],
                "project": project_name,
                "color": color or "#1f77b4"
            }
            tasks_data.append(task_data)
        title = f"Gantt-диаграмма задач: {user_name}\n({date_from} - {date_to})"
        image_bytes = _create_gantt_chart(tasks_data, title)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении Gantt-диаграммы: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении Gantt-диаграммы: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/tasks_by_type",
    summary="Получить pie-диаграмму по типам задач",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения задач по типам за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если задач нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для отображения структуры задач по типам (pie chart) на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_tasks_by_type_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по типам задач: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(TaskType.display_name, func.count(Task.id))
            .join(TaskType, Task.type_id == TaskType.id)
            .where(Task.issue_date >= date_from, Task.issue_date <= date_to)
            .group_by(TaskType.display_name)
        )
        data = [{"label": row[0], "value": row[1]} for row in result.all()]
        title = f"Распределение задач по типам\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по типам задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по типам задач: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/projects_by_type",
    summary="Получить pie-диаграмму по проектам и типам задач",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения задач по типам для выбранного проекта за указанный период.
    
    **Параметры:**
    - `project_id` (int): ID проекта.
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если задач нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для построения pie-диаграмм по проектам и типам задач на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_projects_by_type_image(
    project_id: int = Query(..., description="ID проекта"),
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по проекту и типам задач: project_id={project_id}, date_from={date_from}, date_to={date_to}")
        # Проверка существования проекта
        project = await get_project(db, project_id)
        if not project:
            # Не логируем ошибку, просто возвращаем 404
            raise HTTPException(status_code=404, detail="Проект не найден")
        result = await db.execute(
            select(TaskType.display_name, func.count(Task.id))
            .join(TaskType, Task.type_id == TaskType.id)
            .where(
                Task.project_id == project_id,
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
            .group_by(TaskType.display_name)
        )
        data = [
            {"label": row[0], "value": row[1]}
            for row in result.all()
        ]
        title = f"{project.name}: задачи по типам\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по проекту и типам: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except HTTPException:
        # Позволяем FastAPI корректно обработать 404 и другие HTTP ошибки
        raise
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по проекту и типам: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/reviewers",
    summary="Получить pie-диаграмму по ревьюерам",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения ревью по пользователям за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если данных нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для визуализации активности ревьюеров (pie chart) на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_reviewers_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по ревьюерам: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(User.full_name, User.color, func.count(Review.id)).join(Review, Review.reviewer_id == User.id).where(
                Review.review_date >= date_from,
                Review.review_date <= date_to
            ).group_by(User.full_name, User.color)
        )
        data = [{"label": row[0], "value": row[2], "color": row[1] or '#ff7f0e'}
                for row in result.all()]
        colors = [item['color'] for item in data]
        title = f"Распределение ревью по пользователям\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по ревьюерам: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по ревьюерам: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/testers",
    summary="Получить pie-диаграмму по тестировщикам",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения тестовых периодов по тестировщикам за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если данных нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для построения pie-диаграммы по тестировщикам на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_testers_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по тестировщикам: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(User.full_name, User.color, func.count(Period.id))
            .join(Period, Period.tester_id == User.id)
            .where(
                Period.tester_id.isnot(None),
                Period.start >= date_from,
                Period.end <= date_to
            )
            .group_by(User.full_name, User.color)
        )
        data = [{"label": row[0], "value": row[2], "color": row[1] or '#ff7f0e'}
                for row in result.all()]
        colors = [item['color'] for item in data]
        title = f"Распределение тестовых периодов по тестировщикам\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по тестировщикам: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по тестировщикам: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/sp_by_project",
    summary="Получить pie-диаграмму по story points по проектам",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения story points по проектам за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если данных нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для построения pie-диаграммы story points по проектам на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_sp_by_project_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по story points по проектам: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, Project.name, Project.color)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        project_sp = {}
        project_colors = {}
        for task, project_name, color in result.all():
            extra_fields = task.extra_fields or {}
            sp = extra_fields.get('sp')
            if sp is not None and isinstance(sp, (int, float)):
                project_sp[project_name] = project_sp.get(
                    project_name, 0) + float(sp)
                project_colors[project_name] = color or '#1f77b4'
        data = [
            {"label": project, "value": sp,
                "color": project_colors.get(project, '#1f77b4')}
            for project, sp in project_sp.items()
        ]
        colors = [item['color'] for item in data]
        title = f"Распределение Story Points по проектам\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по story points по проектам: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по story points по проектам: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


# --- PIE: LOC по пользователям ---
@router.get(
    "/pie/loc_by_user",
    summary="Получить pie-диаграмму по строкам кода по пользователям",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения строк кода по пользователям за указанный период.
    """
)
async def get_pie_loc_by_user_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по строкам кода по пользователям: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, User.full_name, User.color)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_loc = defaultdict(int)
        user_colors = {}
        for task, user_name, color in result.all():
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
                user_colors[user_name] = color or '#ff7f0e'
        data = [
            {"label": user, "value": loc,
                "color": user_colors.get(user, '#ff7f0e')}
            for user, loc in user_loc.items() if loc > 0
        ]
        colors = [item['color'] for item in data]
        title = f"Распределение строк кода по пользователям\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по строкам кода: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по строкам кода: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/sp_by_user",
    summary="Получить pie-диаграмму по story points по пользователям",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения story points по пользователям за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если данных нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для построения pie-диаграммы story points по пользователям на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_sp_by_user_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по story points по пользователям: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, User.full_name, User.color)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_sp = defaultdict(float)
        user_colors = {}
        for task, user_name, color in result.all():
            extra_fields = task.extra_fields or {}
            sp = extra_fields.get('sp')
            if sp is not None and isinstance(sp, (int, float)):
                user_sp[user_name] += float(sp)
                user_colors[user_name] = color or '#ff7f0e'
        data = [{"label": user, "value": sp, "color": user_colors.get(
            user, '#ff7f0e')} for user, sp in user_sp.items()]
        colors = [item['color'] for item in data]
        title = f"Распределение Story Points по пользователям\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по story points: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по story points: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/pie/tasks_by_user",
    summary="Получить pie-диаграмму по задачам по пользователям",
    description="""
    Эндпоинт возвращает PNG-изображение pie-диаграммы распределения задач по пользователям за указанный период.
    
    **Параметры:**
    - `date_from` (date): Начальная дата периода (YYYY-MM-DD).
    - `date_to` (date): Конечная дата периода (YYYY-MM-DD).
    
    **Ответ:**
    - PNG-изображение (image/png) с pie-диаграммой.
    - Если данных нет, изображение содержит надпись "Нет данных".
    
    **Использование:**
    - Для построения pie-диаграммы задач по пользователям на фронте.
    - Требуется роль moderator или admin.
    """
)
async def get_pie_tasks_by_user_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Pie-диаграмма по задачам по пользователям: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(User.full_name, User.color, func.count(Task.id)).join(Task, Task.assignee_id == User.id).where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            ).group_by(User.full_name, User.color)
        )
        data = [{"label": row[0], "value": row[2], "color": row[1] or '#ff7f0e'}
                for row in result.all()]
        colors = [item['color'] for item in data]
        title = f"Распределение задач по пользователям\n({date_from} - {date_to})"
        image_bytes = _create_pie_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении pie-диаграммы по задачам по пользователям: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении pie-диаграммы по задачам по пользователям: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/bar/sp_avg_by_user",
    summary="Получить bar-диаграмму по среднему количеству story points по пользователям",
    description="""
    Эндпоинт возвращает PNG-изображение bar-диаграммы среднего количества story points по пользователям за указанный период.
    """
)
async def get_bar_sp_avg_by_user_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Bar-диаграмма по среднему количеству story points: date_from={date_from}, date_to={date_to}")
        result = await db.execute(
            select(Task, User.full_name, User.color)
            .join(User, Task.assignee_id == User.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_sp_data = defaultdict(
            lambda: {"total": 0.0, "count": 0, "color": None})
        for task, user_name, color in result.all():
            extra_fields = task.extra_fields or {}
            sp = extra_fields.get('sp')
            if isinstance(sp, (int, float)):
                user_sp_data[user_name]["total"] += sp
                if sp != 0:
                    user_sp_data[user_name]["count"] += 1
                user_sp_data[user_name]["color"] = color or '#ff7f0e'
        data = []
        for user_name, sp_data in user_sp_data.items():
            if sp_data["count"] > 0:
                avg_sp = sp_data["total"] / sp_data["count"]
                if avg_sp <= 0:
                    continue
                data.append({"label": user_name, "value": round(
                    avg_sp, 2), "color": sp_data["color"] or '#ff7f0e'})
        data.sort(key=lambda x: x["value"], reverse=True)
        colors = [item['color'] for item in data]
        title = f"Среднее количество Story Points по пользователям\n({date_from} - {date_to})"
        image_bytes = _create_bar_chart(data, title, colors=colors)
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении bar-диаграммы по story points: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении bar-диаграммы по story points: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")


@router.get(
    "/bar/aggregate_by_user",
    summary="Bar-диаграмма агрегированного отчета по исполнителям",
    description="""
    Эндпоинт возвращает PNG-изображение bar-диаграммы агрегированного показателя по исполнителям за период (0.25*normalize(tasks) + 0.25*normalize(LOC) + 0.25*normalize(SUM(SP)) + 0.25*normalize(AVG(SP))).
    """
)
async def get_bar_aggregate_by_user_image(
    date_from: date = Query(..., description="Начальная дата периода",
                            example="2024-01-01"),
    date_to: date = Query(..., description="Конечная дата периода",
                          example="2024-01-31"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    try:
        logger.info(
            f"Bar-диаграмма агрегированного отчета: date_from={date_from}, date_to={date_to}")

        def normalize(values: dict[str, float]) -> dict[str, float]:
            if not values:
                return {}
            min_v = min(values.values())
            max_v = max(values.values())
            if max_v == min_v:
                return {k: 1.0 for k in values}
            return {k: (v - min_v) / (max_v - min_v) for k, v in values.items()}
        # Получаем всех пользователей
        users_result = await db.execute(select(User.full_name, User.color))
        user_color_map = {row[0]: row[1]
                          or '#ff7f0e' for row in users_result.all()}
        result = await db.execute(
            select(Task, User.full_name, Project.name)
            .join(User, Task.assignee_id == User.id)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.issue_date >= date_from,
                Task.issue_date <= date_to
            )
        )
        user_tasks = defaultdict(int)
        user_loc = defaultdict(int)
        user_sp_sum = defaultdict(float)
        user_sp_count = defaultdict(int)
        for task, user_name, project_name in result.all():
            user_tasks[user_name] += 1
            extra_fields = task.extra_fields or {}
            loc_plus = extra_fields.get('loc(+)', 0)
            loc_minus = extra_fields.get('loc(-)', 0)
            total_loc = 0
            if isinstance(loc_plus, (int, float)):
                total_loc += loc_plus
            if isinstance(loc_minus, (int, float)):
                total_loc += loc_minus
            user_loc[user_name] += int(total_loc)
            sp = extra_fields.get('sp')
            if isinstance(sp, (int, float)):
                user_sp_sum[user_name] += sp
                if sp != 0:
                    user_sp_count[user_name] += 1
        # --- min/max для нормализаций ---
        task_values = list(user_tasks.values())
        max_tasks = max(task_values, default=1)
        min_tasks = min(task_values, default=0)
        loc_values = [v for v in user_loc.values() if v > 0]
        if loc_values:
            max_loc = max(loc_values)
            min_loc = min(loc_values)
        else:
            max_loc = min_loc = 0
        sp_sum_values = [v for v in user_sp_sum.values() if v > 0]
        if sp_sum_values:
            max_sp_sum = max(sp_sum_values)
            min_sp_sum = min(sp_sum_values)
        else:
            max_sp_sum = min_sp_sum = 0
        # sp_avg
        user_sp_avg = {}
        for u in user_tasks:
            if user_sp_count[u] > 0:
                user_sp_avg[u] = user_sp_sum[u] / user_sp_count[u]
            else:
                user_sp_avg[u] = 0.0
        avg_sp_values = [v for v in user_sp_avg.values() if v > 0]
        if avg_sp_values:
            max_sp_avg = max(avg_sp_values)
            min_sp_avg = min(avg_sp_values)
        else:
            max_sp_avg = min_sp_avg = 0
        # --- нормализации ---
        norm_tasks = {}
        for u in user_tasks:
            if max_tasks == min_tasks:
                norm_tasks[u] = 1.0
            else:
                norm_tasks[u] = (user_tasks[u] - min_tasks) / \
                    (max_tasks - min_tasks)
        norm_loc = {}
        for u in user_loc:
            if max_loc == min_loc:
                norm_loc[u] = 1.0
            else:
                norm_loc[u] = (user_loc[u] - min_loc) / (max_loc - min_loc)
        norm_sp_sum = {}
        for u in user_sp_sum:
            if max_sp_sum == min_sp_sum:
                norm_sp_sum[u] = 1.0
            else:
                norm_sp_sum[u] = (user_sp_sum[u] - min_sp_sum) / \
                    (max_sp_sum - min_sp_sum)
        norm_sp_avg = {}
        for u in user_sp_avg:
            if max_sp_avg == min_sp_avg:
                norm_sp_avg[u] = 1.0
            else:
                norm_sp_avg[u] = (user_sp_avg[u] - min_sp_avg) / \
                    (max_sp_avg - min_sp_avg)
        # --- собираем пользователей с хотя бы одним ненулевым показателем ---
        active_users = [
            u for u in set(user_tasks) | set(user_loc) | set(user_sp_sum) | set(user_sp_count)
            if user_tasks.get(u, 0) > 0 or user_loc.get(u, 0) > 0 or user_sp_sum.get(u, 0) > 0 or user_sp_count.get(u, 0) > 0
        ]
        data = []
        for user in active_users:
            agg = 0.25 * norm_tasks.get(user, 0.0) + 0.25 * norm_loc.get(user, 0.0) + \
                0.25 * norm_sp_sum.get(user, 0.0) + \
                0.25 * norm_sp_avg.get(user, 0.0)
            if agg <= 0:
                continue
            data.append({
                "label": user,
                "value": round(agg, 6),
                "color": user_color_map.get(user, '#ff7f0e'),
                "tasks": user_tasks.get(user, 0),
                "loc": user_loc.get(user, 0),
                "sp_sum": user_sp_sum.get(user, 0.0),
                "sp_avg": round(user_sp_avg.get(user, 0.0), 6),
                "normalize_tasks": round(norm_tasks.get(user, 0.0), 8),
                "normalize_loc": round(norm_loc.get(user, 0.0), 8),
                "normalize_sp_sum": round(norm_sp_sum.get(user, 0.0), 8),
                "normalize_sp_avg": round(norm_sp_avg.get(user, 0.0), 8)
            })
        data.sort(key=lambda x: x["value"], reverse=False)
        # --- bar chart ---
        if not data:
            image_bytes = _create_bar_chart(
                [], "Нет данных для агрегированного отчета")
        else:
            fig, ax = plt.subplots(figsize=(14, max(6, len(data)*0.7)))
            labels = [d["label"] for d in data]
            values = [d["value"] for d in data]
            y_pos = np.arange(len(labels))
            colors = [d["color"] for d in data]
            bars = ax.barh(y_pos, values, color=colors)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=12, fontname="Times New Roman")
            ax.set_xlabel('Агрегированный показатель',
                          fontsize=12, fontname="Times New Roman")
            ax.set_ylabel('Пользователь', fontsize=12,
                          fontname="Times New Roman")
            ax.set_title(
                f"Агрегированный показатель по исполнителям\n({date_from} - {date_to})", fontsize=16, fontweight='bold', pad=20, fontname="Times New Roman")
            # Подписи к барам справа
            for i, (bar, d) in enumerate(zip(bars, data)):
                width = bar.get_width()
                label = (
                    f'{d["value"]:.3f}\n'
                    f'T:{d["tasks"]} L:{d["loc"]} SP:{d["sp_sum"]:.1f}/{d["sp_avg"]:.2f}'
                )
                ax.text(width + 0.01, bar.get_y() + bar.get_height()/2.,
                        label,
                        ha='left', va='center', fontsize=10, fontweight='bold', fontname="Times New Roman")
            plt.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            image_bytes = buf.getvalue()
        return Response(content=image_bytes, media_type="image/png")
    except SQLAlchemyError as e:
        logger.error(
            f"Ошибка базы данных при получении bar-диаграммы агрегированного отчета: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при получении bar-диаграммы агрегированного отчета: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка сервера")
