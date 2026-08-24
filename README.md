# SKBT-UP-GIBDD-SERVER

Backend информационной системы «ГИБДД-Очевидец».

## Технологии

| Раздел | Технология |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL |
| Real-time | WebSocket внутри FastAPI |
| Infrastructure | Linux + systemd + Nginx |

Docker в проекте не используется.

Тестовый API запущен и доступен на публичном порту `4402`:

```text
https://силенок.рф:4402
https://силенок.рф:4402/docs
```

Nginx принимает внешние запросы на порту `4402` и передаёт их FastAPI на внутренний адрес `127.0.0.1:8002`.

## Локальный запуск

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Проверка

```bash
pip install -r requirements-dev.txt
pytest -q
```

## API

Подробный контракт и инструкция для frontend находятся в [docs/api.md](docs/api.md).

- `POST /api/v1/devices/register` — регистрация устройства;
- `GET /api/v1/chats` — список чатов для сотрудника;
- `POST /api/v1/chats/{chat_id}/messages` — отправка сообщения;
- `GET /api/v1/message-templates` — шаблоны ответов сотрудников;
- `POST /api/v1/chats/{chat_id}/messages/template` — ответ сотрудника по шаблону;
- `GET /api/v1/chats/{chat_id}/messages` — история сообщений;
- `PATCH /api/v1/chats/{chat_id}/messages/{message_id}/read` — отметка о прочтении;
- `POST /api/v1/chats/{chat_id}/media` — отправка фото, GIF или видео;
- `GET /api/v1/media/{attachment_id}` — получение медиафайла;
- `POST /api/v1/chats/{chat_id}/locations/static` — статическая геопозиция;
- `POST /api/v1/chats/{chat_id}/locations/live` — запуск live-геопозиции;
- `POST /api/v1/location-sessions/{session_id}/points` — новая live-точка;
- `GET /api/v1/location-sessions/{session_id}` — точки геолокации;
- `PATCH /api/v1/location-sessions/{session_id}/finish` — завершение live-сессии;
- `GET /api/v1/notifications` — уведомления сотрудника;
- `PATCH /api/v1/notifications/{notification_id}/read` — отметка уведомления прочитанным;
- `WS /api/v1/ws/chats/{chat_id}?token={access_token}` — защищённые события чата в реальном времени.
- `POST /api/v1/witnesses/{witness_id}/bans` — выдать бан;
- `GET /api/v1/witnesses/{witness_id}/bans` — история банов;
- `PATCH /api/v1/witnesses/{witness_id}/bans/{ban_id}/revoke` — снять бан.
- `PUT /api/v1/employees/{employee_id}/role` — назначить или изменить роль;
- `PUT /api/v1/devices/{device_id}/role` — назначить роль по `device_id` из QR-кода;
- `DELETE /api/v1/employees/{employee_id}/role` — снять роль;
- `GET /api/v1/employees/{employee_id}/roles/history` — история ролей.

## Развёртывание

Шаблоны для Linux хранятся в `deploy/`:

- `gibdd-backend.service` — systemd unit;
- `nginx.conf` — reverse proxy с поддержкой HTTP и WebSocket.
