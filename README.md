# Workflow Employee

Система управления задачами и проектами для сотрудников.

## Настройка переменных окружения

Перед запуском проекта создайте файл `.env` в корневой директории:

```bash
# Скопируйте пример файла
cp .env.example .env
```

Или создайте файл `.env` вручную со следующим содержимым:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/workflow_employee
DATABASE_URL_TEST=postgresql+asyncpg://postgres:postgres@db:5432/workflow_employee

# Security
SECRET_KEY=your_super_secret_key_change_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# First Superuser
FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_PASSWORD=admin_password
FIRST_SUPERUSER_FULL_NAME=Admin User

# Application Settings
DEBUG=true
LOG_LEVEL=INFO
```

**Важно:**

- Файл `.env` не должен попадать в репозиторий (уже добавлен в `.gitignore`)
- Измените `SECRET_KEY` на уникальное значение в продакшене
- Измените пароли администратора в продакшене

## Импорт данных

Для импорта данных из CSV файлов используйте скрипт `app/db/import_csv.py`:

```bash
python app/db/import_csv.py
```

### Поддерживаемые файлы:

- `projects_2.csv` - проекты
- `ispolnityli_2.csv` - исполнители (пользователи)
- `tasks_2.csv` - задачи с периодами и ревью

### Структура файлов:

**projects_2.csv:**

- Столбец `Проект` - название проекта

**ispolnityli_2.csv:**

- Столбец `Исполнитель` - ФИО пользователя

**tasks_2.csv:**

- `Задача` - название задачи
- `Исполнитель` - ФИО исполнителя
- `Тип` - тип задачи (Backend, Frontend, DevOps, Research, Баг, Прототип интерфейса, Разработка)
- `Выдана` - дата постановки задачи
- `В работе начало` / `В работе конец` - периоды работы
- `В ревью` - дата ревью
- `Ревьювер` - ФИО ревьюера
- `В тестировании` - дата тестирования
- `Тестировщик` - ФИО тестировщика
- ` Ссылка` - ссылка на задачу
- `ПР` - pull request
- `Примечание` - дополнительные заметки
- `Проект` - название проекта
- Дополнительные поля: `LOC (+)`, `LOC (-)`, `LOC`, `SP`, `SP Сухарев`, `SP Голубева`, `SP Аксёнов`

## Запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Применение миграций
alembic upgrade head

# Импорт данных
python -m app.db.import_csv

# Запуск сервера
uvicorn app.main:app --reload
```

## Docker

Для запуска через Docker Compose:

```bash
# Создайте .env файл (см. выше)
# Затем запустите:
docker-compose up -d
```

## API

Документация API доступна по адресу `/docs` после запуска сервера.

### Основные эндпоинты:

- `GET /api/tasks/count` - количество задач (для breadcrumbs)
- `GET /api/tasks/by_project/{project_id}/count` - количество задач по проекту
- `GET /api/tasks/` - список задач
- `GET /api/projects/` - список проектов
