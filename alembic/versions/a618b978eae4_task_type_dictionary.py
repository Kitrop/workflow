"""task type dictionary

Revision ID: a618b978eae4
Revises: 3da75aec9c19
Create Date: 2025-07-02 11:05:39.016117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a618b978eae4'
down_revision: Union[str, Sequence[str], None] = '3da75aec9c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Создаём таблицу task_types
    op.create_table(
        'task_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=64), nullable=False, unique=True),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True)
    )
    # 2. Наполняем начальными типами
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO task_types (id, name, display_name) VALUES
        (1, 'development', 'Разработка'),
        (2, 'research', 'Исследование'),
        (3, 'management', 'Управление')
    """))
    # 3. Добавляем type_id nullable=True
    op.add_column('tasks', sa.Column('type_id', sa.Integer(), nullable=True))
    # 4. Маппим старые значения type -> type_id
    # (Enum -> int)
    conn.execute(sa.text("""
        UPDATE tasks SET type_id = (
            CASE type
                WHEN 'development' THEN 1
                WHEN 'research' THEN 2
                WHEN 'management' THEN 3
                ELSE 1
            END
        )
    """))
    # 5. Делаем type_id NOT NULL
    op.alter_column('tasks', 'type_id', nullable=False)
    # 6. Создаём FK
    op.create_foreign_key(None, 'tasks', 'task_types', ['type_id'], ['id'])
    # 7. Удаляем старое поле type
    op.drop_column('tasks', 'type')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Добавляем обратно поле type (Enum)
    op.add_column('tasks', sa.Column('type', postgresql.ENUM(
        'development', 'research', 'management', name='tasktype'), nullable=False))
    # 2. Маппим обратно type_id -> type
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE tasks SET type = (
            CASE type_id
                WHEN 1 THEN 'development'
                WHEN 2 THEN 'research'
                WHEN 3 THEN 'management'
                ELSE 'development'
            END
        )
    """))
    # 3. Удаляем FK и type_id
    op.drop_constraint(None, 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'type_id')
    # 4. Удаляем справочник
    op.drop_table('task_types')
    # ### end Alembic commands ###
