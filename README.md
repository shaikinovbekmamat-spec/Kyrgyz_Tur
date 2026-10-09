# Kyrgyz Tur

Django-сайт туров по Кыргызстану: каталог, фильтры, регистрация, личный кабинет,
заявки без онлайн-оплаты и управление через Django Admin.

## Запуск

Нужен Python, совместимый с Django 6.1 (3.12 или новее).

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Впишите параметры PostgreSQL и пароль в .env.
# Создайте пустую базу kyrgyz_tur через pgAdmin (Databases → Create → Database).
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py runserver
```

Проект использует PostgreSQL. Параметры подключения находятся в `.env`, который
не включается в Git. Переменные окружения имеют приоритет над значениями файла.
PostgreSQL должен быть запущен; пользователь должен иметь доступ к указанной базе.
Для `manage.py test` требуется право создания тестовой базы.

## Перенос старой SQLite-базы

Остановите сайт на время переноса. Сохраните копию `db.sqlite3`. Экспортируйте
данные старой базы, затем примените миграции и импортируйте их в **пустую**
PostgreSQL-базу, до создания суперпользователя и демонстрационных туров:

```powershell
New-Item -ItemType Directory -Force backups
Copy-Item db.sqlite3 backups/db.sqlite3
.venv/Scripts/python.exe manage.py dumpdata --settings=Kyrgyz_Tur.sqlite_settings --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude sessions --exclude admin.logentry --output backups/sqlite-data.json
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py loaddata backups/sqlite-data.json
.venv/Scripts/python.exe manage.py check
```

Экспорт содержит учётные записи и хеши паролей. Не публикуйте каталог `backups`.
Фотографии остаются в каталоге `media`, их также нужно сохранять при переносе.
Исходная SQLite-база сохраняется; основной сайт больше её не использует.

Откройте http://127.0.0.1:8000/. В `/admin/` добавьте регионы, категории и туры;
внутри тура — фотографии и будущие даты со свободными местами.
Демонстрационные туры можно создать командой `python manage.py seed_demo`.

Пользователь выбирает дату и количество участников. Ожидающая заявка не резервирует
места. В админке выберите заявки и действие «Подтвердить выбранные бронирования».
Система повторно проверяет дату и места, списывает их атомарно. Повторное
подтверждение не списывает места; отмена возвращает их только один раз.
Статус, число участников и дата в существующей заявке доступны только для чтения.
Завершить подтверждённые поездки после их окончания можно отдельным действием.

Подбор ограничивает бюджет на человека и длительность, проверяет стоимость
будущих дат с местами и сортирует по доле совпавших интересов, затем по цене.
Для «горы», «озёра», «культура» используются группы родственных ключевых слов.
Это подбор по словам, а не обработка произвольной фразы с извлечением бюджета.

```powershell
python manage.py check
python manage.py test
```

Настройки рассчитаны на локальную разработку. Для размещения задайте секретный
ключ через окружение, отключите DEBUG и настройте ALLOWED_HOSTS и обслуживание
статических файлов и фотографий.
