# Скрипты управления

Эта папка содержит утилиты для управления системой PC-Guardian.

## add_user.py

Скрипт для добавления пользователей в базу данных.

### Использование

**Создание пользователей по умолчанию:**
```bash
python scripts/add_user.py
```

**Создание пользователя:**
```bash
python scripts/add_user.py <username> <email> <password> [role]
```

**Примеры:**
```bash
# Создать администратора
python scripts/add_user.py admin admin@example.com mypassword admin

# Создать пользователя для просмотра
python scripts/add_user.py user user@example.com mypassword viewer
```

### В Docker контейнере

```bash
docker-compose exec server python /app/scripts/add_user.py
```

## clear_database.py

Скрипт для очистки базы данных от всех данных (сохраняет структуру БД).

**ВНИМАНИЕ:** Удаляет все данные из всех таблиц!

### Использование

**Полная очистка (с подтверждением):**
```bash
python scripts/clear_database.py
```

**Очистка с сохранением пользователей:**
```bash
python scripts/clear_database.py --keep-users
```

**Очистка без подтверждения (для автоматизации):**
```bash
python scripts/clear_database.py --confirm
```

### В Docker контейнере

```bash
# Полная очистка
docker-compose exec server python /app/scripts/clear_database.py

# С сохранением пользователей
docker-compose exec server python /app/scripts/clear_database.py --keep-users
```






