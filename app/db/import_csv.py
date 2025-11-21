import pandas as pd
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.project import Project
from app.models.user import User, UserRole
from app.models.task import Task
from app.models.task_type import TaskType
from app.db.base import Base
import math
# импортируем функцию хеширования пароля
from app.auth import get_password_hash
import random
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Создание engine и сессии ---
engine = create_engine(settings.DATABASE_URL.replace('asyncpg', 'psycopg2'))
SessionLocal = sessionmaker(bind=engine)


def random_color() -> str:
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))


def safe_read_csv(filename: str, sep: str = ';'):
    """
    Безопасное чтение CSV файла с обработкой ошибок
    """
    try:
        df = pd.read_csv(filename, sep=sep)
        logger.info(f"Успешно прочитан файл {filename}: {len(df)} строк")
        return df
    except FileNotFoundError:
        logger.error(f"Файл {filename} не найден")
        raise
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {filename}: {e}")
        raise


def safe_parse_date(val):
    """
    Безопасный парсинг даты с улучшенной обработкой ошибок
    """
    if pd.isna(val) or val in [None, '', '-', 'NaT', 'nan']:
        return None
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            logger.warning(f"Не удалось распарсить дату: {val}")
            return None
        return dt
    except Exception as e:
        logger.warning(f"Ошибка при парсинге даты '{val}': {e}")
        return None


def clean_extra_fields(fields: dict) -> dict:
    """
    Очистка дополнительных полей с улучшенной обработкой
    """
    try:
        return {
            k: (None if (pd.isna(v) or v is None or (
                isinstance(v, float) and math.isnan(v))) else v)
            for k, v in fields.items()
        }
    except Exception as e:
        logger.warning(f"Ошибка при очистке полей: {e}")
        return {}


def import_projects(session):
    """
    Импорт проектов с улучшенной обработкой ошибок
    """
    try:
        df = safe_read_csv('projects_2.csv', sep=';')
        imported_count = 0
        skipped_count = 0
        
        for index, row in df.iterrows():
            try:
                name = str(row['Проект']).strip()
                if not name or name.lower().startswith('итого') or name.lower() == 'nan':
                    skipped_count += 1
                    continue
                
                project = session.query(Project).filter_by(name=name).first()
                if not project:
                    project = Project(name=name, description=None, color=random_color())
                    session.add(project)
                    imported_count += 1
                    logger.debug(f"Добавлен проект: {name}")
                else:
                    logger.debug(f"Проект уже существует: {name}")
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке строки {index + 1}: {e}")
                continue
        
        session.commit()
        logger.info(f'Проекты импортированы: {imported_count} новых, {skipped_count} пропущено')
        
    except Exception as e:
        logger.error(f"Критическая ошибка при импорте проектов: {e}")
        session.rollback()
        raise


def import_users(session):
    """
    Импорт пользователей с улучшенной обработкой ошибок
    """
    try:
        df = safe_read_csv('ispolnityli_2.csv', sep=';')
        imported_count = 0
        skipped_count = 0
        
        for index, row in df.iterrows():
            try:
                full_name = str(row['Исполнитель']).strip()
                if not full_name or full_name.lower() in ['итого', 'nan']:
                    skipped_count += 1
                    continue
                
                user = session.query(User).filter_by(full_name=full_name).first()
                if not user:
                    username = full_name.replace(' ', '_').lower()
                    # Устанавливаем одинаковый пароль для всех
                    hashed_password = get_password_hash('passord@1234')
                    user = User(
                        username=username,
                        hashed_password=hashed_password,
                        full_name=full_name,
                        role=UserRole.user,
                        can_load_tasks=True,
                        can_view_reports=True,
                        color=random_color()
                    )
                    session.add(user)
                    imported_count += 1
                    logger.debug(f"Добавлен пользователь: {full_name}")
                else:
                    logger.debug(f"Пользователь уже существует: {full_name}")
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя в строке {index + 1}: {e}")
                continue
        
        session.commit()
        logger.info(f'Пользователи импортированы: {imported_count} новых, {skipped_count} пропущено')
        
    except Exception as e:
        logger.error(f"Критическая ошибка при импорте пользователей: {e}")
        session.rollback()
        raise


def import_manager(session):
    """
    Поиск менеджера с улучшенной обработкой ошибок
    """
    try:
        # Находим первого пользователя с ролью admin или просто первого пользователя
        manager = session.query(User).filter_by(role=UserRole.admin).first()
        if not manager:
            manager = session.query(User).first()
        
        if manager:
            logger.info(f"Найден менеджер: {manager.full_name}")
        else:
            logger.warning("Менеджер не найден, задачи будут созданы без менеджера")
            
        return manager
        
    except Exception as e:
        logger.error(f"Ошибка при поиске менеджера: {e}")
        return None


def import_tasks(session):
    """
    Импорт задач с улучшенной обработкой ошибок
    """
    try:
        df = safe_read_csv('tasks_2.csv', sep=';')
        manager = import_manager(session)
        imported_count = 0
        skipped_count = 0
        error_count = 0
        
        for index, row in df.iterrows():
            try:
                name = str(row['Задача']).strip()
                if not name or name.lower() == 'nan':
                    skipped_count += 1
                    continue
                
                # Поиск исполнителя
                assignee_name = str(row['Исполнитель']).strip()
                assignee = None
                if assignee_name and assignee_name != 'nan':
                    assignee = session.query(User).filter_by(full_name=assignee_name).first()
                    if not assignee:
                        logger.warning(f"Исполнитель не найден: {assignee_name}")
                
                # Поиск проекта
                project_name = str(row['Проект']).strip()
                project = None
                if project_name and project_name != 'nan':
                    project = session.query(Project).filter_by(name=project_name).first()
                    if not project:
                        logger.warning(f"Проект не найден: {project_name}")
                
                # Маппинг типа задачи
                type_map = {
                    'Прототип интерфейса': 'development',
                    'Функционал': 'development',
                    'Рефакторинг': 'development',
                    'Развёртывание': 'management',
                    'Баг': 'research',
                    'Документация': 'management',
                    'Макеты': 'research',
                    'Backend': 'development',
                    'Frontend': 'development',
                    'DevOps': 'management',
                    'Research': 'research',
                    'Разработка': 'development'
                }
                
                type_str = str(row['Тип']).strip()
                type_code = type_map.get(type_str, 'development')
                task_type = session.query(TaskType).filter_by(name=type_code).first()
                
                if not task_type:
                    logger.warning(f"Тип задачи '{type_code}' не найден в справочнике, используется 'development'")
                    task_type = session.query(TaskType).filter_by(name='development').first()
                    if not task_type:
                        logger.error("Тип задачи 'development' не найден в справочнике")
                        error_count += 1
                        continue
                
                # Дата постановки задачи
                issue_date = safe_parse_date(row['Выдана'])
                if not issue_date:
                    logger.warning(f"Не удалось распарсить дату постановки для задачи: {name}")
                    issue_date = pd.Timestamp.now().date()  # Используем текущую дату
                
                # Ссылка
                issue_url = None
                for key in [' Ссылка', 'Ссылка']:
                    if key in row and not pd.isna(row[key]) and str(row[key]).strip():
                        issue_url = str(row[key]).strip()
                        break
                
                # Дополнительные поля
                extra_fields = clean_extra_fields({
                    'loc(+)': row.get('LOC (+)', None),
                    'loc(-)': row.get('LOC (-)', None),
                    'loc': row.get('LOC', None),
                    'sp': row.get('SP', None),
                    'pr': row.get('ПР', None)
                })
                
                # Проверка на дубли
                task = session.query(Task).filter_by(
                    name=name, issue_date=issue_date, assignee_id=assignee.id if assignee else None).first()
                
                if not task:
                    task = Task(
                        name=name,
                        type_id=task_type.id,
                        issue_url=issue_url,
                        issue_date=issue_date,
                        assignee_id=assignee.id if assignee else None,
                        project_id=project.id if project else None,
                        manager_id=manager.id if manager else None,
                        extra_fields=extra_fields
                    )
                    session.add(task)
                    session.flush()  # Получаем task.id для связей
                    
                    # Импорт периодов
                    try:
                        from app.models.task import Period, PeriodType
                        
                        # В работе
                        work_start = safe_parse_date(row.get('В работе начало', None))
                        work_end = safe_parse_date(row.get('В работе конец', None))
                        if work_start and work_end:
                            period = Period(
                                task_id=task.id,
                                start=work_start,
                                end=work_end,
                                type=PeriodType.work,
                                tester_id=None
                            )
                            session.add(period)
                            logger.debug(f"Добавлен период работы для задачи: {name}")
                        
                        # В тестировании
                        test_start = safe_parse_date(row.get('В тестировании', None))
                        test_end = None
                        tester_name = row.get('Тестировщик', None)
                        if test_start:
                            tester = None
                            if tester_name and tester_name != 'nan':
                                tester = session.query(User).filter_by(full_name=tester_name).first()
                            
                            period = Period(
                                task_id=task.id,
                                start=test_start,
                                end=test_end if test_end else test_start,
                                type=PeriodType.test,
                                tester_id=tester.id if tester else None
                            )
                            session.add(period)
                            logger.debug(f"Добавлен период тестирования для задачи: {name}")
                            
                    except Exception as e:
                        logger.error(f"Ошибка при импорте периодов для задачи '{name}': {e}")
                    
                    # Импорт ревью
                    try:
                        from app.models.task import Review
                        review_date = safe_parse_date(row.get('В ревью', None))
                        reviewer_name = row.get('Ревьювер', None)
                        
                        if review_date and reviewer_name and reviewer_name != 'nan':
                            reviewer = session.query(User).filter_by(full_name=reviewer_name).first()
                            if reviewer:
                                review = Review(
                                    task_id=task.id,
                                    reviewer_id=reviewer.id,
                                    review_date=review_date
                                )
                                session.add(review)
                                logger.debug(f"Добавлено ревью для задачи: {name}")
                            else:
                                logger.warning(f"Ревьюер не найден: {reviewer_name}")
                                
                    except Exception as e:
                        logger.error(f"Ошибка при импорте ревью для задачи '{name}': {e}")
                    
                    imported_count += 1
                    logger.debug(f"Добавлена задача: {name}")
                else:
                    logger.debug(f"Задача уже существует: {name}")
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке задачи в строке {index + 1}: {e}")
                error_count += 1
                continue
        
        session.commit()
        logger.info(f'Задачи импортированы: {imported_count} новых, {skipped_count} пропущено, {error_count} ошибок')
        
    except Exception as e:
        logger.error(f"Критическая ошибка при импорте задач: {e}")
        session.rollback()
        raise


def main():
    """
    Главная функция с улучшенной обработкой ошибок
    """
    session = None
    try:
        logger.info("Начинаем импорт данных...")
        session = SessionLocal()
        
        logger.info("Импорт проектов...")
        import_projects(session)
        
        logger.info("Импорт пользователей...")
        import_users(session)
        
        logger.info("Импорт задач...")
        import_tasks(session)
        
        logger.info("Импорт завершён успешно!")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при импорте: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()


if __name__ == '__main__':
    main()
