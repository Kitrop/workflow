from sqlalchemy import (Column, Integer, String, Boolean, ForeignKey, Table,
                        DateTime, func)
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.dialects.postgresql import UUID

# --- Ассоциативная таблица для доступа пользователей к проектам ---
user_project_association_table = Table(
    'user_project_access', Base.metadata,
    Column('user_id', UUID(as_uuid=True),
           ForeignKey('users.id'), primary_key=True),  # ID пользователя
    Column('project_id', Integer, ForeignKey(
        'projects.id'), primary_key=True),  # ID проекта
    Column('granted_by_id', UUID(as_uuid=True), ForeignKey(
        'users.id')),         # Кто выдал доступ
    Column('granted_at', DateTime, default=func.now()
           )                           # Когда выдан доступ
)

# --- Модель проекта ---


class Project(Base):
    __tablename__ = "projects"

    # Уникальный идентификатор проекта
    id = Column(Integer, primary_key=True, index=True)
    # Название проекта
    name = Column(String, unique=True, index=True)
    # Описание проекта
    description = Column(String)
    is_public = Column(Boolean, default=False,
                       nullable=False)   # Публичный ли проект
    color = Column(String(16), default="#1f77b4", nullable=False)  # Цвет проекта (hex)

    # --- Связи ---
    tasks = relationship("Task", back_populates="project",
                         cascade="all, delete-orphan")  # Задачи проекта

    # Связь с пользователями, имеющими доступ
    users_with_access = relationship(
        "User",
        secondary=user_project_association_table,
        back_populates="accessible_projects",
        foreign_keys=[user_project_association_table.c.project_id,
                      user_project_association_table.c.user_id]
    )  # Пользователи с доступом к проекту
