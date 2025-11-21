from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.project import Project, user_project_association_table
from app.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectUpdate
from sqlalchemy import or_, and_

# --- CRUD-операции для проектов ---


async def create_project(db: AsyncSession, project_in: ProjectCreate) -> Project:
    """
    Создаёт новый проект в базе данных.
    """
    project = Project(
        name=project_in.name,
        description=project_in.description,
        is_public=project_in.is_public,
        color=project_in.color or "#1f77b4"
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, project_id: int) -> Optional[Project]:
    """
    Получает проект по ID, включая пользователей с доступом.
    """
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.users_with_access))
        .where(Project.id == project_id)
    )
    return result.scalars().first()


async def get_user_accessible_projects(db: AsyncSession, user: User) -> List[Project]:
    """
    Получает список проектов, доступных пользователю (учитывает публичность и доступы).
    """
    if user.role == UserRole.admin:
        # Админ видит все проекты
        result = await db.execute(select(Project))
        return result.scalars().all()
    else:
        # Пользователь видит публичные проекты и те, к которым у него есть доступ
        query = (
            select(Project)
            .join(user_project_association_table, isouter=True)
            .where(
                or_(
                    Project.is_public == True,
                    user_project_association_table.c.user_id == user.id
                )
            )
            .distinct()
        )
        result = await db.execute(query)
        return result.scalars().all()


async def update_project(db: AsyncSession, project: Project, project_in: ProjectUpdate) -> Project:
    """
    Обновляет данные проекта.
    """
    project_data = project_in.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project):
    """
    Удаляет проект из базы данных.
    """
    await db.delete(project)
    await db.commit()


async def can_user_access_project(db: AsyncSession, user: User, project: Project) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к проекту.
    """
    if user.role == UserRole.admin or project.is_public:
        return True
    # Проверяем, есть ли пользователь в списке доступов
    query = (
        select(user_project_association_table)
        .where(
            and_(
                user_project_association_table.c.user_id == user.id,
                user_project_association_table.c.project_id == project.id
            )
        )
    )
    result = await db.execute(query)
    return result.first() is not None


async def grant_access_to_user(db: AsyncSession, project: Project, user: User, admin_user: User):
    """
    Выдаёт пользователю доступ к проекту.
    """
    if user not in project.users_with_access:
        project.users_with_access.append(user)
        # В Alembic миграции нет granted_by_id, поэтому эта часть закомментирована
        # stmt = user_project_association_table.update().where(...).values(granted_by_id=admin_user.id)
        # await db.execute(stmt)
        await db.commit()


async def revoke_access_from_user(db: AsyncSession, project: Project, user: User):
    """
    Отзывает у пользователя доступ к проекту.
    """
    if user in project.users_with_access:
        project.users_with_access.remove(user)
        await db.commit()


async def get_project_by_name(db: AsyncSession, name: str) -> Optional[Project]:
    """
    Получает проект по имени.
    """
    result = await db.execute(select(Project).where(Project.name == name))
    return result.scalars().first()
