from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from uuid import UUID
from passlib.context import CryptContext
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Хеширует пароль для хранения в базе.
    """
    return pwd_context.hash(password)


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    Создаёт нового пользователя в базе данных.
    """
    user = User(
        username=user_in.username,
        full_name=user_in.full_name,
        role=user_in.role,
        hashed_password=get_password_hash(user_in.password),
        color=user_in.color or "#ff7f0e"
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    Получает пользователя по username.
    """
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()


async def get_user(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """
    Получает пользователя по UUID.
    """
    return await db.get(User, user_id)


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    """
    Получает список пользователей с пагинацией.
    """
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


async def update_user(db: AsyncSession, user: User, user_in: UserCreate) -> User:
    """
    Обновляет данные пользователя.
    """
    user.username = user_in.username
    user.full_name = user_in.full_name
    user.role = user_in.role
    user.hashed_password = get_password_hash(user_in.password)
    user.color = user_in.color or "#ff7f0e"
    await db.flush()
    await db.refresh(user)
    return user


async def update_user_partial(db: AsyncSession, user: User, user_in: UserUpdate) -> User:
    """
    Частичное обновление данных пользователя (PATCH). Теперь можно менять username, если он уникален.
    """
    if user_in.username is not None and user_in.username != user.username:
        # Проверка уникальности
        from sqlalchemy import select
        from app.models.user import User as UserModel
        result = await db.execute(select(UserModel).where(UserModel.username == user_in.username))
        existing = result.scalars().first()
        if existing:
            raise ValueError("Пользователь с таким username уже существует")
        user.username = user_in.username
    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.color is not None:
        user.color = user_in.color
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user: User):
    """
    Удаляет пользователя из базы данных.
    """
    await db.delete(user)
    await db.flush()
