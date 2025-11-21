from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.autocomplete import router as autocomplete_router
from app.api.reports import router as reports_router
from app.api.report_images import router as report_images_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(projects_router, prefix="/projects", tags=["projects"])
router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
router.include_router(autocomplete_router,
                      prefix="/autocomplete", tags=["autocomplete"])
router.include_router(reports_router, prefix="/reports", tags=["reports"])
router.include_router(report_images_router,
                      prefix="/report-images", tags=["report-images"])
