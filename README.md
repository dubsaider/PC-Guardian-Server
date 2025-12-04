# PC-Guardian Server

Серверная часть системы мониторинга комплектующих ПК PC-Guardian.

## Возможности

- Kafka Consumer для получения данных от агентов
- Сравнение конфигураций и обнаружение изменений
- Веб-интерфейс на FastAPI
- Система оповещений (Telegram, Email)
- База данных для хранения конфигураций и событий

## Установка

1. Установите Python 3.8 или выше
2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Инициализируйте базу данных:
```bash
python init_db.py
```

## Конфигурация

### База данных

По умолчанию используется SQLite. Для использования PostgreSQL:

```env
DATABASE_URL=postgresql://user:password@localhost/pcguardian
```

### Kafka

Настройте подключение к Kafka через переменные окружения (в `docker-compose.yml` или `.env`):

```env
KAFKA_BOOTSTRAP_SERVERS=10.53.16.49:9092
KAFKA_TOPIC=pc-guardian-configs
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
```

При использовании Docker Compose все настройки уже заданы в `docker-compose.yml`. По умолчанию используется IP адрес `10.53.16.49` для внешнего доступа к Kafka.

Если нужно изменить IP адрес, создайте файл `docker-compose.override.yml` и укажите другой адрес:
```yaml
services:
  kafka:
    environment:
      KAFKA_ADVERTISED_HOST: ваш_ip_адрес
```

### Уведомления

#### Telegram:
1. Создайте бота через @BotFather
2. Получите токен и chat_id
3. Добавьте в `.env`:
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

#### Email:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=admin@example.com
```

## Запуск

### С помощью Docker Compose (рекомендуется)

1. Запустите все сервисы:
```bash
docker-compose up -d
```

2. Проверьте статус:
```bash
docker-compose ps
```

3. Просмотрите логи:
```bash
docker-compose logs -f server
```

Сервисы будут доступны:
- **Server**: http://localhost:8000
- **Kafka UI**: http://localhost:8080 (мониторинг Kafka)
- **Kafka**: 10.53.16.49:9092 (для внешних клиентов)

### Локальный запуск

```bash
python app.py
```

Или через uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Сервер будет доступен по адресу: http://localhost:8000

**Примечание:** При локальном запуске убедитесь, что Kafka запущен и доступен.

## Пользователи по умолчанию

После инициализации БД создаются пользователи:
- `admin/admin` - администратор
- `viewer/viewer` - просмотр

**Важно:** Измените пароли после первого входа!

### Создание пользователей вручную

Если пользователи не были созданы автоматически, используйте скрипт:

```bash
# Локально
python scripts/add_user.py

# В Docker контейнере
docker-compose exec server python /app/scripts/add_user.py
```

См. `scripts/README.md` для подробной информации.

## API Endpoints

### Web Interface
- `GET /` - Дашборд
- `GET /pc/{pc_id}` - Детальная информация о ПК
- `GET /events` - Журнал событий

### API
- `GET /api/pcs` - Список ПК
- `GET /api/pcs/{pc_id}` - Информация о ПК
- `GET /api/pcs/{pc_id}/events` - События ПК
- `POST /api/pcs/{pc_id}/baseline` - Установить эталонную конфигурацию
- `GET /api/events` - Все события
- `GET /api/stats` - Статистика

## Структура проекта

```
PC-Guardian-Server/
├── app.py                 # FastAPI приложение
├── database.py            # Модели БД
├── kafka_consumer.py      # Kafka Consumer
├── config_comparator.py   # Сравнение конфигураций
├── notifications.py       # Система оповещений
├── auth.py                # Аутентификация
├── init_db.py             # Инициализация БД
├── common/                # Общие модули
│   ├── models.py
│   └── kafka_config.py
├── scripts/               # Утилиты
│   ├── add_user.py        # Добавление пользователей
│   └── README.md
├── templates/             # HTML шаблоны
│   ├── base.html
│   ├── dashboard.html
│   ├── pc_detail.html
│   ├── events.html
│   └── login.html
├── docker-compose.yml     # Docker Compose конфигурация
├── Dockerfile             # Docker образ
└── requirements.txt       # Python зависимости
```

## Docker Compose

### Структура сервисов

- **zookeeper** - Zookeeper для Kafka (порт 2181)
- **kafka** - Kafka брокер (порт 9092)
- **kafka-ui** - Веб-интерфейс для мониторинга Kafka (порт 8080)
- **server** - PC-Guardian Server (порт 8000)

### Управление

```bash
# Запуск всех сервисов
docker-compose up -d

# Остановка всех сервисов
docker-compose down

# Пересборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Просмотр логов конкретного сервиса
docker-compose logs -f server
docker-compose logs -f kafka

# Остановка и удаление volumes
docker-compose down -v
```

### Настройка через переменные окружения

Создайте файл `docker-compose.override.yml` (на основе `docker-compose.override.yml.example`) для настройки:
- Telegram уведомлений
- Email уведомлений
- PostgreSQL вместо SQLite

## Разработка

Для разработки с автоматической перезагрузкой:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Разработка с Docker

Для разработки можно монтировать код в контейнер:

```yaml
# В docker-compose.override.yml
services:
  server:
    volumes:
      - .:/app
      - /app/__pycache__
    command: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

