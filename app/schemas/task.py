from __future__ import annotations
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID

from app.models.task import PeriodType


# --- Схемы периодов задачи ---
class PeriodBase(BaseModel):
    start: date = Field(..., description="Дата начала периода",
                        example="2024-01-01")  # Начало периода
    end: date = Field(..., description="Дата окончания периода",
                      example="2024-01-10")  # Окончание периода
    type: PeriodType = Field(...,
                             # Тип периода
                             description="Тип периода (work/test)", example="work")
    tester_id: Optional[UUID] = Field(
        None, description="ID тестировщика", example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")  # Тестировщик


class PeriodCreate(PeriodBase):
    pass  # Использует все поля базовой схемы


class PeriodOut(PeriodBase):
    id: int = Field(..., description="ID периода",
                    example=1)  # Уникальный идентификатор

    class Config:
        from_attributes = True


# --- Схемы ревью задачи ---
class ReviewBase(BaseModel):
    reviewer_id: UUID = Field(..., description="ID ревьюера",
                              example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")  # Ревьюер
    review_date: date = Field(..., description="Дата ревью",
                              example="2024-01-15")  # Дата ревью


class ReviewCreate(ReviewBase):
    pass  # Использует все поля базовой схемы


class ReviewOut(ReviewBase):
    # Уникальный идентификатор
    id: int = Field(..., description="ID ревью", example=1)

    class Config:
        from_attributes = True


# --- Схема типа задачи ---
class TaskTypeOut(BaseModel):
    id: int = Field(..., description="ID типа задачи", example=1)
    name: str = Field(..., description="Код типа задачи (machine name)",
                      example="development")
    display_name: str = Field(
        ..., description="Человекочитаемое название типа задачи", example="Разработка")
    description: Optional[str] = Field(
        None, description="Описание типа задачи", example="Задачи, связанные с разработкой функционала")

    class Config:
        from_attributes = True


# --- Схемы задачи ---
class TaskBase(BaseModel):
    name: str = Field(..., description="Название задачи", max_length=256,
                      example="Реализация авторизации")  # Название задачи
    type_id: int = Field(
        ..., description="ID типа задачи (ссылка на справочник)", example=1)
    issue_url: Optional[str] = Field(
        # Ссылка на задачу
        None, description="URL задачи в трекере", example="https://example.com/browse/PROJ-1")
    issue_date: date = Field(..., description="Дата создания задачи",
                             example="2024-01-01")  # Дата создания
    assignee_id: UUID = Field(..., description="ID исполнителя",
                              example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")  # Исполнитель
    project_id: int = Field(..., description="ID проекта", example=1)  # Проект
    manager_id: UUID = Field(..., description="ID менеджера",
                             example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")  # Менеджер


class TaskCreate(TaskBase):
    periods: List[PeriodCreate] = Field(...,
                                        description="Список периодов задачи")  # Периоды
    reviews: Optional[List[ReviewCreate]] = Field(
        None, description="Список ревью задачи")  # Ревью
    extra_fields: Dict[str, Any] = Field(
        {}, description="Дополнительные поля для задачи")  # Доп. поля


class TaskOut(TaskBase):
    id: int = Field(..., description="ID задачи",
                    example=1)  # Уникальный идентификатор
    extra_fields: Dict[str, Any] = Field(
        {}, description="Дополнительные поля для задачи")  # Доп. поля
    periods: List[PeriodOut] = Field(
        [], description="Список периодов задачи")  # Периоды
    reviews: List[ReviewOut] = Field(
        [], description="Список ревью задачи")  # Ревью
    task_type: Optional[TaskTypeOut] = Field(
        None, description="Объект типа задачи (справочник)")

    class Config:
        from_attributes = True


# --- Схема истории изменений задачи ---
class TaskHistoryOut(BaseModel):
    id: int = Field(..., description="ID записи истории",
                    example=1)  # Уникальный идентификатор
    task_id: int = Field(..., description="ID задачи", example=1)  # Задача
    changed_by_id: UUID = Field(..., description="ID пользователя, изменившего задачу",
                                example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")  # Кто изменил
    changed_at: datetime = Field(..., description="Дата и время изменения",
                                 example="2024-01-02T12:00:00")  # Когда изменено
    field: str = Field(..., description="Измененное поле",
                       example="status")  # Поле
    old_value: Optional[str] = Field(
        None, description="Старое значение", example="open")  # Было
    new_value: Optional[str] = Field(
        None, description="Новое значение", example="closed")  # Стало
    # Информация о пользователе, который внес изменения
    changed_by_username: Optional[str] = Field(
        None, description="Имя пользователя, внесшего изменение", example="john_doe")

    class Config:
        from_attributes = True


# --- Схема количества задач ---
class TaskCountOut(BaseModel):
    total_count: int = Field(..., description="Общее количество задач", example=150)
    project_count: Optional[int] = Field(None, description="Количество задач в проекте", example=25)
    
    class Config:
        from_attributes = True
