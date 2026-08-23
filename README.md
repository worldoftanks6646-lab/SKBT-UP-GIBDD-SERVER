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
http://193.124.115.164:4402
http://193.124.115.164:4402/docs
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
- `GET /api/v1/chats/{chat_id}/messages` — история сообщений;
- `PATCH /api/v1/chats/{chat_id}/messages/{message_id}/read` — отметка о прочтении;
- `WS /api/v1/ws/chats/{chat_id}?device_id={device_id}` — события чата в реальном времени.
- `POST /api/v1/witnesses/{witness_id}/bans` — выдать бан;
- `GET /api/v1/witnesses/{witness_id}/bans` — история банов;
- `PATCH /api/v1/witnesses/{witness_id}/bans/{ban_id}/revoke` — снять бан.
- `PUT /api/v1/employees/{employee_id}/role` — назначить или изменить роль;
- `DELETE /api/v1/employees/{employee_id}/role` — снять роль;
- `GET /api/v1/employees/{employee_id}/roles/history` — история ролей.

## Развёртывание

Шаблоны для Linux хранятся в `deploy/`:

- `gibdd-backend.service` — systemd unit;
- `nginx.conf` — reverse proxy с поддержкой HTTP и WebSocket.
