# API Reference — WorkFlow Employee

## Базовая информация

- **Базовый URL:** `http://localhost:8000/api`
- **Авторизация:** Bearer Token (JWT)
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Формат ответов:** JSON

---

## Авторизация

- Для большинства эндпоинтов требуется JWT-токен.
- Получить токен можно через POST `/api/auth/token` (username + password).
- Токен передается в заголовке:
  ```http
  Authorization: Bearer <your_token>
  ```

---

## Пример стандартного ответа

```json
{
	"id": 1,
	"name": "CRM Backend",
	"description": "Система управления клиентами",
	"is_public": true
}
```

## Пример ошибки

```json
{
	"detail": "Проект с таким именем уже существует"
}
```

---

## Основные эндпоинты

### Аутентификация

#### POST `/api/auth/token`

- Получить JWT-токен по username и password (form-data).
- Ответ: `{ "access_token": "...", "token_type": "bearer" }`

### Пользователи

- `GET /api/users/` — список пользователей (только для admin)
- `POST /api/users/` — создать пользователя (только для admin)
- `GET /api/users/me` — получить свой профиль
- `GET /api/users/{user_id}` — получить пользователя по ID
- `PUT /api/users/{user_id}` — обновить пользователя (только для admin)
- `DELETE /api/users/{user_id}` — удалить пользователя (только для admin)

#### Пример создания пользователя

```json
{
	"username": "ivanov",
	"password": "secret123",
	"full_name": "Иван Иванов",
	"role": "user"
}
```

### Проекты

- `GET /api/projects/` — список проектов
- `POST /api/projects/` — создать проект (только для admin)
- `GET /api/projects/{project_id}` — получить проект по ID
- `PUT /api/projects/{project_id}` — обновить проект (только для admin)
- `DELETE /api/projects/{project_id}` — удалить проект (только для admin)
- `POST /api/projects/{project_id}/access?user_id=...` — выдать доступ пользователю (admin)
- `DELETE /api/projects/{project_id}/access/{user_id}` — отозвать доступ (admin)
- `GET /api/projects/{project_id}/users` — пользователи с доступом (admin)

#### Пример создания проекта

```json
{
	"name": "CRM Backend",
	"description": "Система управления клиентами",
	"is_public": true
}
```

### Задачи

- `GET /api/tasks/` — список задач
- `POST /api/tasks/` — создать задачу
- `GET /api/tasks/{task_id}` — получить задачу по ID
- `PUT /api/tasks/{task_id}` — обновить задачу
- `DELETE /api/tasks/{task_id}` — удалить задачу
- `GET /api/tasks/count` — получить количество задач (для breadcrumbs)
- `GET /api/tasks/by_project/{project_id}` — задачи по проекту
- `GET /api/tasks/by_project/{project_id}/count` — количество задач по проекту
- `GET /api/tasks/{task_id}/history` — история изменений задачи

#### Пример создания задачи

```json
{
	"name": "Реализация авторизации",
	"type": "development",
	"issue_url": "https://exampole.com/browse/PROJ-1",
	"issue_date": "2024-01-01",
	"assignee_id": "b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a",
	"project_id": 1,
	"manager_id": "b3b7c7e2-8e2a-4c2a-9e2a-4c2a9e2a4c2a",
	"periods": [{ "start": "2024-01-01", "end": "2024-01-10", "type": "work" }],
	"reviews": [],
	"extra_fields": {}
}
```

### Отчеты

- `GET /api/reports/gantt` — Gantt-отчет по задачам пользователя
- `GET /api/reports/pie/tasks_by_type` — Pie-отчет по типам задач
- `GET /api/reports/pie/projects_by_type` — Pie-отчет по проектам и типам задач
- `GET /api/reports/pie/reviewers` — Pie-отчет по ревьюерам
- `GET /api/reports/pie/testers` — Pie-отчет по тестировщикам
- `GET /api/reports/pie/sp_by_project` — Pie-отчет по story points по проектам
- `GET /api/reports/pie/loc_by_user` — Pie-отчет по строкам кода по пользователям
- `GET /api/reports/pie/sp_by_user` — Pie-отчет по story points по пользователям
- `GET /api/reports/pie/tasks_by_user` — Pie-отчет по задачам по пользователям
- `GET /api/reports/bar/sp_avg_by_user` — Bar-отчет по среднему количеству story points по пользователям

### Изображения отчетов

- `GET /api/report-images/gantt` — Gantt-диаграмма по задачам пользователя (PNG)
- `GET /api/report-images/pie/tasks_by_type` — Pie-диаграмма по типам задач (PNG)
- `GET /api/report-images/pie/projects_by_type` — Pie-диаграмма по проектам и типам задач (PNG)
- `GET /api/report-images/pie/reviewers` — Pie-диаграмма по ревьюерам (PNG)
- `GET /api/report-images/pie/testers` — Pie-диаграмма по тестировщикам (PNG)
- `GET /api/report-images/pie/sp_by_project` — Pie-диаграмма по story points по проектам (PNG)
- `GET /api/report-images/pie/loc_by_user` — Pie-диаграмма по строкам кода по пользователям (PNG)
- `GET /api/report-images/pie/sp_by_user` — Pie-диаграмма по story points по пользователям (PNG)
- `GET /api/report-images/pie/tasks_by_user` — Pie-диаграмма по задачам по пользователям (PNG)
- `GET /api/report-images/bar/sp_avg_by_user` — Bar-диаграмма по среднему количеству story points по пользователям (PNG)

**Примечание:** Все эндпоинты изображений возвращают PNG-файлы напрямую. Для получения изображения используйте параметры `date_from` и `date_to` для указания периода. Gantt-диаграмма дополнительно требует параметр `user_id` для указания пользователя.

### Автодополнение

- `GET /api/autocomplete/users?query=...` — пользователи по имени/логину
- `GET /api/autocomplete/projects?query=...` — проекты по названию
- `GET /api/autocomplete/managers?query=...` — менеджеры (админы) по имени/логину

---

## Пояснения по бизнес-логике

- **Роли:** admin, user (и расширяемые роли)
- **Доступ к проектам:** через таблицу user_project_access
- **JWT-аутентификация:** все защищенные эндпоинты требуют Bearer Token
- **Права на отчеты и загрузку задач:** через флаги can_load_tasks, can_view_reports
- **История изменений задач:** хранится в task_history

---

## Инструменты

- Swagger UI: `/docs`
- Alembic: миграции БД
- Docker
