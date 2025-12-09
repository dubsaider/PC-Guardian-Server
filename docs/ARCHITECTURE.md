# Архитектура PC-Guardian Server

## Обзор

Проект использует комбинированный подход: **layered architecture** + **feature-based organization**.

## Структура проекта

```
PC-Guardian-Server/
├── api/                    # API слой (REST endpoints)
│   ├── routes/            # API роутеры по функциональности
│   │   ├── pcs.py         # Управление ПК
│   │   ├── events.py      # События
│   │   ├── stats.py       # Статистика
│   │   └── auth.py        # Аутентификация
│   ├── schemas/           # Pydantic схемы для валидации
│   └── dependencies.py    # FastAPI зависимости
│
├── web/                    # Web слой (HTML страницы)
│   └── routes/            # Web роутеры
│       ├── dashboard.py   # Дашборд
│       ├── pc_detail.py   # Детали ПК
│       └── events.py       # Журнал событий
│
├── core/                   # Бизнес-логика (Domain Layer)
│   ├── domain/            # Domain модели и логика
│   │   └── comparators/   # Компараторы для сравнения
│   └── services/         # Сервисы бизнес-логики
│       ├── pc_service.py
│       ├── config_service.py
│       ├── event_service.py
│       └── configuration_processing_service.py
│
├── infrastructure/         # Инфраструктурный слой
│   ├── database/         # Работа с БД
│   │   ├── models.py     # SQLAlchemy модели
│   │   ├── repositories/ # Репозитории (Data Access Layer)
│   │   └── session.py    # Сессии БД
│   ├── kafka/            # Kafka интеграция
│   └── messaging/        # Система уведомлений
│
├── common/                 # Общие модули
│   ├── models.py         # Domain модели (dataclasses)
│   └── location_parser.py
│
└── scripts/               # Утилиты и миграции
    └── migrations/       # Миграции БД
```

## Слои архитектуры

### 1. API Layer (`api/`)
- **Ответственность**: HTTP endpoints, валидация запросов, форматирование ответов
- **Зависимости**: Использует `core/services` и `infrastructure/repositories`
- **Не содержит**: Бизнес-логику, прямую работу с БД

### 2. Web Layer (`web/`)
- **Ответственность**: HTML страницы, рендеринг шаблонов
- **Зависимости**: Использует `api/routes` или напрямую `core/services`

### 3. Core Layer (`core/`)
- **Ответственность**: Вся бизнес-логика приложения
- **Структура**:
  - `domain/` - Domain модели и бизнес-правила
  - `services/` - Сервисы, координирующие бизнес-логику
- **Зависимости**: Использует `infrastructure/repositories`
- **Не содержит**: Детали реализации (БД, HTTP, Kafka)

### 4. Infrastructure Layer (`infrastructure/`)
- **Ответственность**: Технические детали реализации
- **Структура**:
  - `database/` - SQLAlchemy модели, репозитории
  - `kafka/` - Kafka consumer/producer
  - `messaging/` - Система уведомлений
- **Не содержит**: Бизнес-логику

## Модели данных

### Текущее состояние vs История

#### `PCCurrentConfiguration` (текущее состояние)
- **Назначение**: Быстрый доступ к текущему состоянию ПК
- **Хранение**: Одна запись на ПК (обновляется при каждом изменении)
- **Использование**: API для списка ПК, дашборд

#### `PCConfiguration` (история изменений)
- **Назначение**: Полная история всех изменений конфигурации
- **Хранение**: Множество записей на ПК (append-only)
- **Использование**: История изменений, граф изменений, аудит

### Преимущества разделения

1. **Производительность**: 
   - Список ПК загружает только текущее состояние (1 запрос вместо N)
   - История загружается только когда нужна

2. **Масштабируемость**:
   - Текущее состояние - маленькая таблица (1 запись на ПК)
   - История может расти без ограничений

3. **Функциональность**:
   - Легко построить граф изменений
   - Можно отслеживать изменения по компонентам
   - Временной анализ изменений

## Поток данных

```
Kafka Message
    ↓
Kafka Consumer
    ↓
ConfigurationProcessingService
    ↓
├─→ PCConfiguration (история) - сохраняется всегда
└─→ PCCurrentConfiguration (текущее) - обновляется
    ↓
EventService (создает события изменений)
```

## Feature-based организация (будущее)

Для больших фич можно создать feature-модули:

```
features/
├── pc_management/        # Управление ПК
│   ├── api/
│   ├── services/
│   └── repositories/
├── history_tracking/     # Отслеживание истории
│   ├── api/
│   ├── services/
│   └── repositories/
└── alerts/               # Система алертов
    ├── api/
    ├── services/
    └── repositories/
```

## Миграции

Все миграции БД находятся в `scripts/migrations/` и выполняются вручную или через скрипты.

## Принципы

1. **Dependency Inversion**: Высокоуровневые модули не зависят от низкоуровневых
2. **Single Responsibility**: Каждый модуль имеет одну ответственность
3. **Separation of Concerns**: Четкое разделение слоев
4. **DRY**: Избегание дублирования кода

