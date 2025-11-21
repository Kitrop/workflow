from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import UUID
from app.models.user import UserRole

# --- Базовая схема пользователя ---


class UserBase(BaseModel):
    username: str = Field(...,
                          max_length=32,
                          description="Уникальный логин пользователя", example="ivanov")  # Логин
    full_name: Optional[str] = Field(
        None, max_length=64, description="Полное имя пользователя", example="Иван Иванов")  # ФИО
    role: UserRole = Field(
        # Роль
        UserRole.user, description="Роль пользователя (admin или user)", example="user")
    color: str = Field(
        "#ff7f0e", min_length=4, max_length=16, description="Цвет пользователя (hex)", example="#ff7f0e")

    class Config:
        extra = "forbid"  # Запрещает лишние поля


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128, description="Пароль пользователя",
                          example="secret123")  # Пароль

    class Config:
        extra = "forbid"


class UserUpdate(BaseModel):
    username: Optional[str] = Field(
        None, max_length=32, description="Уникальный логин пользователя (можно изменить, если не занят)", example="ivanov")
    full_name: Optional[str] = Field(
        None, max_length=64, description="Полное имя пользователя", example="Иван Иванов")
    role: Optional[UserRole] = Field(
        None, description="Роль пользователя (admin или user)", example="user")
    color: Optional[str] = Field(
        None, min_length=4, max_length=16, description="Цвет пользователя (hex)", example="#ff7f0e")
    password: Optional[str] = Field(
        None, min_length=6, max_length=128, description="Пароль пользователя", example="secret123")

    class Config:
        extra = "forbid"


class UserOut(UserBase):
    id: UUID = Field(..., description="ID пользователя",
                     example="b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a")  # Уникальный идентификатор

    class Config:
        from_attributes = True  # Позволяет создавать схему из ORM-модели
