import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import get_user_by_username, create_user
from app.schemas.user import UserCreate
from app.core.config import settings
from app.models.user import UserRole

# Настройка логгера для инициализации данных
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_db(db: AsyncSession) -> None:
    """
    Инициализация базы данных начальными данными.
    Создаёт суперпользователя, если его нет.
    """
    # Проверка, существует ли суперпользователь
    user = await get_user_by_username(db, username=settings.FIRST_SUPERUSER_USERNAME)
    if not user:
        logger.info("Создание первого суперпользователя")
        user_in = UserCreate(
            # Логин суперпользователя из настроек
            username=settings.FIRST_SUPERUSER_USERNAME,
            # Пароль суперпользователя из настроек
            password=settings.FIRST_SUPERUSER_PASSWORD,
            # Имя суперпользователя из настроек
            full_name=settings.FIRST_SUPERUSER_FULL_NAME,
            role=UserRole.admin,  # Роль: администратор
        )
        # Создание пользователя
        user = await create_user(db=db, user_in=user_in)
        await db.commit()  # Сохраняем изменения
        logger.info("Первый суперпользователь создан")
    else:
        logger.info("Суперпользователь уже существует, создание пропущено")
