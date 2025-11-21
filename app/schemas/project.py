from pydantic import BaseModel, Field
from typing import Optional, List

# --- Базовая схема проекта ---


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=64, description="Название проекта",
                      example="CRM Backend")  # Название
    description: Optional[str] = Field(
        None, max_length=256, description="Описание проекта", example="Система управления клиентами")  # Описание
    is_public: bool = Field(
        False, description="Публичный ли проект", example=True)  # Флаг публичности
    color: str = Field(
        "#1f77b4", min_length=4, max_length=16, description="Цвет проекта (hex)", example="#1f77b4")

    class Config:
        extra = "forbid"

# --- Схема создания проекта ---


class ProjectCreate(ProjectBase):
    class Config:
        extra = "forbid"

# --- Схема обновления проекта ---


class ProjectUpdate(ProjectBase):
    name: Optional[str] = Field(
        None, max_length=64, description="Название проекта", example="CRM Backend")  # Новое название
    description: Optional[str] = Field(
        None, max_length=256, description="Описание проекта", example="Система управления клиентами")
    is_public: Optional[bool] = Field(
        None, description="Публичный ли проект", example=True)  # Новый флаг публичности
    color: Optional[str] = Field(
        None, min_length=4, max_length=16, description="Цвет проекта (hex)", example="#1f77b4")

    class Config:
        extra = "forbid"

# --- Схема проекта для вывода ---


class ProjectOut(ProjectBase):
    id: int = Field(..., description="ID проекта",
                    example=1)  # Уникальный идентификатор

    class Config:
        from_attributes = True  # Позволяет создавать схему из ORM-модели
