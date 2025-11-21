from sqlalchemy import Column, Integer, String, Text
from app.db.base import Base


class TaskType(Base):
    __tablename__ = "task_types"
    id = Column(Integer, primary_key=True)
    # machine name (например, "development")
    name = Column(String(64), unique=True, nullable=False)
    # человекочитаемое название (например, "Разработка")
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
