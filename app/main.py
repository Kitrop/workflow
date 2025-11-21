from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from app.api import router as api_router
from app.db import AsyncSessionLocal
from app.db.initial_data import init_db
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
import logging
import sys
import traceback
from app.core.config import settings

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    stream=sys.stdout
)
logger = logging.getLogger("workflow_employee")

app = FastAPI(
    title=settings.PROJECT_NAME
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные обработчики исключений


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Обработчик ошибок валидации Pydantic"""
    logger.warning(f"Ошибка валидации: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Ошибка валидации данных",
            "errors": exc.errors()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений"""
    logger.warning(f"HTTP ошибка {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Обработчик ошибок базы данных"""
    logger.error(f"Ошибка базы данных: {str(exc)}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка базы данных"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Общий обработчик всех остальных исключений"""
    logger.error(f"Неожиданная ошибка: {str(exc)}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера"}
    )


@app.on_event("startup")
async def on_startup():
    logger.info("[STARTUP] Запуск приложения...")
    db = AsyncSessionLocal()
    try:
        await init_db(db)
    finally:
        await db.close()
    logger.info("[STARTUP] Приложение успешно запущено.")

# Заглушка для корневого эндпоинта


@app.get("/")
async def root():
    return {"message": "WorkFlow Employee API"}


@app.get("/health")
async def health_check():
    """Эндпоинт для проверки здоровья приложения"""
    return {"status": "healthy"}

app.include_router(api_router, prefix="/api")
