"""
FastAPI приложение для PC-Guardian Server
"""
import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from infrastructure.database.session import Base, engine
from infrastructure.kafka.config import KafkaConfig
from infrastructure.kafka.consumer import PCGuardianConsumer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаем таблицы БД
Base.metadata.create_all(bind=engine)

# Инициализация Kafka Consumer
kafka_config = KafkaConfig()
consumer = None


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования всех HTTP запросов"""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(f"→ {request.method} {request.url.path}")
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(f"← {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"✗ {request.method} {request.url.path} - ERROR: {e} ({process_time:.3f}s)")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global consumer
    # Запуск при старте
    consumer = PCGuardianConsumer(kafka_config)
    consumer.start()
    yield
    # Остановка при завершении
    if consumer:
        consumer.stop()


app = FastAPI(
    title="PC-Guardian Server",
    description="Система мониторинга комплектующих ПК",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware для логирования запросов
app.add_middleware(LoggingMiddleware)

# Статические файлы
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== Подключение роутеров ====================

# API роутеры
from api.routes.health import router as health_router
from api.routes.auth import router as auth_router
from api.routes.pcs import router as pcs_router
from api.routes.events import router as events_router
from api.routes.stats import router as stats_router
from api.routes.alert_rules import router as alert_rules_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(pcs_router)
app.include_router(events_router)
app.include_router(stats_router)
app.include_router(alert_rules_router)

# Web роутеры
from web.routes.dashboard import router as dashboard_router
from web.routes.pc_detail import router as pc_detail_router
from web.routes.events import router as events_web_router
from web.routes.history import router as history_router
from web.routes.alert_rules import router as alert_rules_web_router

app.include_router(dashboard_router)
app.include_router(pc_detail_router)
app.include_router(events_web_router)
app.include_router(history_router)
app.include_router(alert_rules_web_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
