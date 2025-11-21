import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.crud.user import get_user_by_username
from app.core.config import settings
from app.db import get_db
from app.models.user import User, UserRole
from app.models.project import Project

# Настройка логгера для отслеживания ошибок аутентификации и авторизации
logger = logging.getLogger(__name__)

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# OAuth2 схема для авторизации через JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
# HTTP Bearer схема для авторизации
security = HTTPBearer()


def verify_password(plain_password, hashed_password):
    """
    Проверяет соответствие пароля и его хэша.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    Хеширует пароль для хранения в базе.
    """
    return pwd_context.hash(password)


async def authenticate_user(db: AsyncSession, username: str, password: str):
    """
    Аутентифицирует пользователя по username и паролю.
    Возвращает пользователя или None, если не найден/неверный пароль.
    """
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        logger.warning(f"Неудачная попытка входа: {username}")
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Создаёт JWT-токен с заданными данными и временем жизни.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(
            timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Получает текущего пользователя по JWT-токену из заголовка Authorization.
    Бросает HTTP 401, если токен невалиден или пользователь не найден.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[
                             settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("JWT payload не содержит sub")
            raise credentials_exception
    except JWTError:
        logger.warning("Ошибка декодирования JWT")
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if user is None:
        logger.warning(f"Пользователь не найден по username: {username}")
        raise credentials_exception
    return user


def check_task_loading_permission(user: User) -> bool:
    """
    Проверяет, может ли пользователь загружать задачи.
    """
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.task_loader:
        return True
    return user.can_load_tasks


def check_report_viewing_permission(user: User) -> bool:
    """
    Проверяет, может ли пользователь просматривать отчёты.
    """
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.moderator:
        return True

    return user.can_view_reports


async def require_task_loading_permission(current_user: User = Depends(get_current_user)) -> User:
    """
    Декоратор для эндпоинтов, требующих права на загрузку задач.
    """
    if not check_task_loading_permission(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для загрузки задач"
        )
    return current_user


async def require_report_viewing_permission(current_user: User = Depends(get_current_user)) -> User:
    """
    Декоратор для эндпоинтов, требующих права на просмотр отчётов.
    """
    if not check_report_viewing_permission(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра отчетов"
        )
    return current_user


async def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Декоратор для эндпоинтов, требующих прав администратора.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав. Требуются права администратора."
        )
    return current_user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Возвращает текущего активного пользователя (заглушка для совместимости).
    """
    return current_user


async def require_project_access(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    if current_user.role == UserRole.admin:
        return
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalars().first()
    if not project or current_user not in project.users_with_access:
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к этому проекту"
        )
