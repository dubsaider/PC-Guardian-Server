# Docker Guide для PC-Guardian Server

## Быстрый старт

1. Клонируйте репозиторий и перейдите в директорию Server
2. Запустите все сервисы:
```bash
docker-compose up -d
```

3. Дождитесь запуска всех сервисов (около 30-60 секунд)
4. Откройте в браузере:
   - **PC-Guardian Server**: http://localhost:8000
   - **Kafka UI**: http://localhost:8080

## Структура сервисов

### Zookeeper
- **Порт**: 2181
- **Назначение**: Координация Kafka кластера
- **Healthcheck**: Проверка доступности на порту 2181

### Kafka
- **Порт**: 9092 (внешний), 29092 (внутренний)
- **Назначение**: Брокер сообщений для получения данных от агентов
- **Healthcheck**: Проверка API версий брокера
- **Автосоздание топиков**: Включено

### Kafka UI
- **Порт**: 8080
- **Назначение**: Веб-интерфейс для мониторинга Kafka
- **Функции**:
  - Просмотр топиков и сообщений
  - Мониторинг consumer groups
  - Просмотр метрик

### Server
- **Порт**: 8000
- **Назначение**: PC-Guardian Server (FastAPI)
- **Volumes**:
  - `./data` - база данных SQLite
  - `./logs` - логи приложения
- **Healthcheck**: Проверка доступности API

## Управление

### Запуск
```bash
# Запуск в фоновом режиме
docker-compose up -d

# Запуск с выводом логов
docker-compose up
```

### Остановка
```bash
# Остановка сервисов
docker-compose stop

# Остановка и удаление контейнеров
docker-compose down

# Остановка с удалением volumes (удалит БД!)
docker-compose down -v
```

### Логи
```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f server
docker-compose logs -f kafka
docker-compose logs -f zookeeper
```

### Пересборка
```bash
# Пересборка образа сервера
docker-compose build server

# Пересборка и перезапуск
docker-compose up -d --build server
```

### Статус
```bash
# Статус всех сервисов
docker-compose ps

# Детальная информация
docker-compose ps -a
```

## Настройка

### Переменные окружения

Создайте файл `docker-compose.override.yml` для настройки:

```yaml
version: '3.8'

services:
  server:
    environment:
      # Telegram
      TELEGRAM_BOT_TOKEN: your_token
      TELEGRAM_CHAT_ID: your_chat_id
      
      # Email
      SMTP_HOST: smtp.gmail.com
      SMTP_PORT: 587
      SMTP_USER: your_email@gmail.com
      SMTP_PASSWORD: your_app_password
      EMAIL_FROM: your_email@gmail.com
      EMAIL_TO: admin@example.com
```

### Использование PostgreSQL

Добавьте в `docker-compose.override.yml`:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: pc-guardian-postgres
    environment:
      POSTGRES_USER: pcguardian
      POSTGRES_PASSWORD: pcguardian_password
      POSTGRES_DB: pcguardian
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - pc-guardian-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pcguardian"]
      interval: 10s
      timeout: 5s
      retries: 5

  server:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://pcguardian:pcguardian_password@postgres:5432/pcguardian

volumes:
  postgres-data:
```

## Troubleshooting

### Сервер не запускается

1. Проверьте логи:
```bash
docker-compose logs server
```

2. Убедитесь, что Kafka доступен:
```bash
docker-compose logs kafka
```

3. Проверьте healthcheck:
```bash
docker-compose ps
```

### Kafka не подключается

1. Проверьте, что Kafka запущен:
```bash
docker-compose ps kafka
```

2. Проверьте логи Kafka:
```bash
docker-compose logs kafka
```

3. Проверьте через Kafka UI: http://localhost:8080

### Проблемы с базой данных

1. Проверьте права на директорию `data`:
```bash
ls -la data/
```

2. Удалите старую БД и пересоздайте:
```bash
rm -rf data/
docker-compose up -d
```

### Порт уже занят

Если порты 8000, 8080, 9092 заняты, измените их в `docker-compose.yml`:

```yaml
services:
  server:
    ports:
      - "8001:8000"  # Вместо 8000:8000
```

## Разработка

### Монтирование кода для разработки

Добавьте в `docker-compose.override.yml`:

```yaml
services:
  server:
    volumes:
      - .:/app
      - /app/__pycache__
    command: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Теперь изменения в коде будут автоматически применяться.

### Доступ к контейнеру

```bash
# Войти в контейнер сервера
docker-compose exec server bash

# Выполнить команду
docker-compose exec server python init_db.py
```

## Мониторинг

### Kafka UI

Откройте http://localhost:8080 для:
- Просмотра топиков
- Мониторинга сообщений
- Просмотра consumer groups
- Метрик производительности

### Healthchecks

Все сервисы имеют healthchecks. Проверьте статус:
```bash
docker-compose ps
```

Здоровые сервисы покажут `(healthy)` в статусе.

## Производительность

### Оптимизация Kafka

Для продакшена настройте в `docker-compose.yml`:

```yaml
kafka:
  environment:
    KAFKA_NUM_PARTITIONS: 6
    KAFKA_DEFAULT_REPLICATION_FACTOR: 2
```

### Ресурсы

Минимальные требования:
- CPU: 2 ядра
- RAM: 2 GB
- Disk: 10 GB

Рекомендуемые для продакшена:
- CPU: 4 ядра
- RAM: 4 GB
- Disk: 50 GB

