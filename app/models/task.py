import enum

from sqlalchemy import (Column, Date, DateTime, Enum, ForeignKey, Integer,
                        JSON, String, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

# --- Модель задачи ---


class Task(Base):
    __tablename__ = "tasks"
    # Уникальный идентификатор задачи
    id = Column(Integer, primary_key=True)
    type_id = Column(Integer, ForeignKey("task_types.id"), nullable=False)
    # Название задачи
    name = Column(String, nullable=False)
    # Ссылка на задачу в трекере
    issue_url = Column(String)
    # Дата постановки задачи
    issue_date = Column(Date, nullable=False)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id"))      # ID исполнителя
    project_id = Column(Integer, ForeignKey(
        "projects.id"))               # ID проекта
    manager_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id"))       # ID менеджера
    # Дополнительные поля для типа задачи
    extra_fields = Column(JSON, default={})
    # --- Связи ---
    assignee = relationship(
        # Исполнитель
        "User", back_populates="tasks", foreign_keys=[assignee_id], lazy="selectin")
    project = relationship("Project", back_populates="tasks",
                           lazy="selectin")        # Проект
    manager = relationship(
        # Менеджер
        "User", back_populates="managed_tasks", foreign_keys=[manager_id], lazy="selectin")
    periods = relationship(
        # Периоды работы/тестирования
        "Period", back_populates="task", cascade="all, delete-orphan", lazy="selectin")
    reviews = relationship(
        # Ревью задачи
        "Review", back_populates="task", cascade="all, delete-orphan", lazy="selectin")
    history = relationship(
        # История изменений
        "TaskHistory", back_populates="task", cascade="all, delete-orphan", lazy="selectin")
    task_type = relationship("TaskType")

# --- Перечисление типов периодов ---


class PeriodType(str, enum.Enum):
    work = "work"  # Рабочий период
    test = "test"  # Тестовый период

# --- Модель периода ---


class Period(Base):
    __tablename__ = "periods"
    # Уникальный идентификатор периода
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"),
                     nullable=False)     # ID задачи
    # Дата начала
    start = Column(Date)
    # Дата окончания
    end = Column(Date)
    # Тип периода
    type = Column(Enum(PeriodType), nullable=False)
    tester_id = Column(UUID(as_uuid=True),
                       # ID тестировщика
                       ForeignKey("users.id"), nullable=True)
    # --- Связи ---
    task = relationship("Task", back_populates="periods",
                        lazy="selectin")           # Задача
    tester = relationship("User", back_populates="tested_periods",
                          # Тестировщик
                          foreign_keys=[tester_id], lazy="selectin")

# --- Модель ревью ---


class Review(Base):
    __tablename__ = "reviews"
    # Уникальный идентификатор ревью
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"),
                     nullable=False)     # ID задачи
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id"))      # ID ревьюера
    # Дата ревью
    review_date = Column(Date)
    # --- Связи ---
    task = relationship("Task", back_populates="reviews",
                        lazy="selectin")           # Задача
    reviewer = relationship(
        # Ревьюер
        "User", back_populates="reviewed_tasks", foreign_keys=[reviewer_id], lazy="selectin")

# --- Модель истории изменений задачи ---


class TaskHistory(Base):
    __tablename__ = "task_history"
    # Уникальный идентификатор записи истории
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id")
                     )                     # ID задачи
    changed_by_id = Column(UUID(as_uuid=True), ForeignKey(
        "users.id"))    # ID пользователя, внёсшего изменение
    changed_at = Column(DateTime, server_default=func.now()
                        )               # Дата и время изменения
    # Изменённое поле
    field = Column(String)
    # Старое значение
    old_value = Column(String)
    # Новое значение
    new_value = Column(String)
    # --- Связи ---
    task = relationship("Task", back_populates="history",
                        lazy="selectin")           # Задача
    # Кто изменил
    changed_by = relationship("User", lazy="selectin")
