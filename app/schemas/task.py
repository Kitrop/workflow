from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID

from app.models.task import PeriodType


# --- Схемы периодов задачи ---
class PeriodBase(BaseModel):
    start: date = Field(..., description="Дата начала периода",
                        example="2024-01-01")
    end: date = Field(..., description="Дата окончания периода",
                      example="2024-01-10")
    type: PeriodType = Field(...,
                             description="Тип периода (work/test)", example="work")
    tester_id: Optional[UUID] = Field(
        None, description="ID тестировщика", example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")


class PeriodCreate(PeriodBase):
    pass


class PeriodOut(PeriodBase):
    id: int = Field(..., description="ID периода", example=1)

    class Config:
        from_attributes = True


# --- Схемы ревью задачи ---
class ReviewBase(BaseModel):
    reviewer_id: UUID = Field(..., description="ID ревьюера",
                              example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")
    review_date: date = Field(..., description="Дата ревью",
                              example="2024-01-15")


class ReviewCreate(ReviewBase):
    pass


class ReviewOut(ReviewBase):
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
                      example="Реализация авторизации")
    type_id: int = Field(
        ..., description="ID типа задачи (ссылка на справочник)", example=1)
    issue_url: Optional[str] = Field(
        None, description="URL задачи в трекере", example="https://example.com/browse/PROJ-1")
    issue_date: date = Field(..., description="Дата создания задачи",
                             example="2024-01-01")
    
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: Добавлен Optional и default=None ---
    assignee_id: Optional[UUID] = Field(
        None, description="ID исполнителя", example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")
    
    project_id: Optional[int] = Field(
        None, description="ID проекта", example=1)
    
    manager_id: Optional[UUID] = Field(
        None, description="ID менеджера", example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")


class TaskCreate(TaskBase):
    periods: List[PeriodCreate] = Field(..., description="Список периодов задачи")
    reviews: Optional[List[ReviewCreate]] = Field(
        None, description="Список ревью задачи")
    extra_fields: Dict[str, Any] = Field(
        {}, description="Дополнительные поля для задачи")


class TaskOut(TaskBase):
    id: int = Field(..., description="ID задачи", example=1)
    extra_fields: Dict[str, Any] = Field(
        {}, description="Дополнительные поля для задачи")
    periods: List[PeriodOut] = Field(
        [], description="Список периодов задачи")
    reviews: List[ReviewOut] = Field(
        [], description="Список ревью задачи")
    task_type: Optional[TaskTypeOut] = Field(
        None, description="Объект типа задачи (справочник)")

    class Config:
        from_attributes = True


# --- Схема истории изменений задачи ---
class TaskHistoryOut(BaseModel):
    id: int = Field(..., description="ID записи истории", example=1)
    task_id: int = Field(..., description="ID задачи", example=1)
    changed_by_id: UUID = Field(..., description="ID пользователя, изменившего задачу",
                                example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")
    changed_at: datetime = Field(..., description="Дата и время изменения",
                                 example="2024-01-02T12:00:00")
    field: str = Field(..., description="Измененное поле", example="status")
    old_value: Optional[str] = Field(
        None, description="Старое значение", example="open")
    new_value: Optional[str] = Field(
        None, description="Новое значение", example="closed")
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