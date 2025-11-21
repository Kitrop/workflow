import enum
import uuid

from sqlalchemy import Column, Enum, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.project import user_project_association_table

# --- Перечисление ролей пользователя ---


class UserRole(str, enum.Enum):
    admin = "admin"  # Администратор
    moderator = "moderator"  # Модератор (может просматривать отчёты)
    user = "user"    # Обычный пользователь

# --- Модель пользователя ---


class User(Base):
    __tablename__ = "users"

    # Уникальный идентификатор пользователя
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Логин пользователя
    username = Column(String, unique=True, nullable=False)
    # Хэш пароля
    hashed_password = Column(String, nullable=False)
    # Полное имя
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.user,
                  nullable=False)  # Роль пользователя
    # Может ли загружать задачи
    can_load_tasks = Column(Boolean, default=False, nullable=False)
    # Может ли просматривать отчёты
    can_view_reports = Column(Boolean, default=False, nullable=False)
    color = Column(String(16), default="#ff7f0e",
                   nullable=False)  # Цвет пользователя (hex)

    # --- Связи ---
    tasks = relationship("Task", back_populates="assignee",
                         foreign_keys="Task.assignee_id")  # Задачи, назначенные пользователю
    managed_tasks = relationship(
        # Задачи, которыми управляет пользователь
        "Task", back_populates="manager", foreign_keys="Task.manager_id")
    reviewed_tasks = relationship(
        "Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")  # Проведённые ревью
    tested_periods = relationship(
        # Протестированные периоды
        "Period", back_populates="tester", foreign_keys="Period.tester_id")
    accessible_projects = relationship(
        "Project",
        secondary="user_project_access",
        back_populates="users_with_access",
        foreign_keys=[user_project_association_table.c.user_id,
                      user_project_association_table.c.project_id]
    )  # Проекты, к которым у пользователя есть доступ
