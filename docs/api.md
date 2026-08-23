# API «ГИБДД-Очевидец»

Документ предназначен для разработчиков Android-приложений Очевидца и Сотрудника. Он описывает только реализованный API.

## Подключение

Публичный тестовый сервер запущен и доступен по адресу:

```text
http://193.124.115.164:4402
```

Состояние на 21 августа 2026 года:

- PostgreSQL подключён, миграции применены;
- FastAPI запущен как служба systemd;
- Nginx принимает внешние запросы на порту `4402`;
- регистрация, повторный вход, создание чата, отправка и получение сообщений проверены через публичный адрес;
- Docker не используется.

Для Retrofit адрес должен заканчиваться `/`:

```kotlin
const val BASE_URL = "http://193.124.115.164:4402/"
```

Swagger и OpenAPI:

```text
http://193.124.115.164:4402/docs
http://193.124.115.164:4402/openapi.json
```

Пока используется HTTP. Для тестового APK добавьте в `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />

<application
    android:usesCleartextTraffic="true"
    ...>
</application>
```

Для production потребуется HTTPS, после чего WebSocket-адрес изменится с `ws://` на `wss://`.

## Общие правила

- запросы и ответы используют JSON;
- UUID передаются строками;
- даты передаются в ISO 8601 с часовым поясом;
- fingerprint создаётся на Android и передаётся как SHA-256 из 64 hex-символов;
- при регистрации frontend сохраняет полученные `device_id`, `witness_id`, `employee_id` и `chat_id`;
- access-токены в текущей версии ещё не реализованы, поэтому идентификатор устройства передаётся в запросе;
- `400`, `403`, `404`, `409` содержат поле `detail`, а ошибки валидации возвращают `422`.

## Реализованные маршруты

```text
GET    /api/health
POST   /api/v1/devices/register

GET    /api/v1/chats
POST   /api/v1/chats/{chat_id}/messages
GET    /api/v1/chats/{chat_id}/messages
PATCH  /api/v1/chats/{chat_id}/messages/{message_id}/read
WS     /api/v1/ws/chats/{chat_id}?device_id={device_id}

POST   /api/v1/witnesses/{witness_id}/bans
GET    /api/v1/witnesses/{witness_id}/bans
PATCH  /api/v1/witnesses/{witness_id}/bans/{ban_id}/revoke

PUT    /api/v1/employees/{employee_id}/role
DELETE /api/v1/employees/{employee_id}/role
GET    /api/v1/employees/{employee_id}/roles/history
```

## GET /api/health

Проверяет доступность backend. Авторизация не нужна.

```bash
curl http://193.124.115.164:4402/api/health
```

Ответ `200 OK`:

```json
{
  "status": "ok",
  "service": "gibdd-backend",
  "version": "1.0.0"
}
```

## POST /api/v1/devices/register

Регистрирует устройство очевидца или сотрудника.

```json
{
  "fingerprint_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "type": "witness",
  "platform": "android",
  "app_version": "1.0.0"
}
```

Допустимые типы:

```text
witness  — Очевидец
employee — Сотрудник
```

Ответ для нового очевидца (`201 Created`):

```json
{
  "device_id": "0759db59-5263-41c2-a6fc-e16d8cc76f95",
  "type": "witness",
  "is_new": true,
  "witness_id": "4b4f5672-888e-49a9-8e44-d0052a2e7830",
  "employee_id": null,
  "role": null,
  "chat_id": "65cb767f-d939-466e-beaf-8334c97f0612",
  "ban_level": 0
}
```

Ответ для первого сотрудника:

```json
{
  "device_id": "4502a5b0-905d-4160-b4c5-f1b470e0e494",
  "type": "employee",
  "is_new": true,
  "witness_id": null,
  "employee_id": "8fc9c6b2-33aa-4d60-bb94-a24b648f2a3e",
  "role": "chief",
  "chat_id": null,
  "ban_level": null
}
```

Первый сотрудник автоматически получает `chief`. Следующие сотрудники создаются без роли.

При повторной регистрации backend возвращает тот же `device_id`, обновляет платформу и версию приложения, а `is_new` становится `false`.

Ошибки:

- `409` — зарегистрированное устройство пытается сменить `type`;
- `422` — fingerprint не состоит ровно из 64 hex-символов или поле заполнено неправильно.

## POST /api/v1/chats/{chat_id}/messages

Создаёт текстовое сообщение.

```json
{
  "sender_device_id": "0759db59-5263-41c2-a6fc-e16d8cc76f95",
  "text": "Сообщение очевидца"
}
```

Ответ `201 Created`:

```json
{
  "id": "42626038-9eb9-4915-acc3-f425e8d575cd",
  "chat_id": "65cb767f-d939-466e-beaf-8334c97f0612",
  "sender_device_id": "0759db59-5263-41c2-a6fc-e16d8cc76f95",
  "sender_type": "witness",
  "message_type": "text",
  "text": "Сообщение очевидца",
  "sent_at": "2026-08-20T07:14:09Z",
  "read_at": null,
  "deleted": false
}
```

Текст должен содержать от 1 до 4000 символов после удаления пробелов по краям.

Ошибки:

- `403` — устройство не имеет доступа к этому чату;
- `404` — чат или устройство не найдено;
- `422` — неверный UUID или пустой текст.

## GET /api/v1/chats

Возвращает сотруднику с активной ролью список чатов, отсортированный от самого свежего к самому старому.

```text
GET /api/v1/chats?requester_device_id={device_id}&limit=50
```

Параметры:

- `requester_device_id` — `device_id` сотрудника;
- `limit` — от 1 до 100, по умолчанию 50;
- `before` — необязательная дата ISO 8601 для следующей страницы.

Ответ:

```json
{
  "items": [
    {
      "id": "65cb767f-d939-466e-beaf-8334c97f0612",
      "witness_id": "4b4f5672-888e-49a9-8e44-d0052a2e7830",
      "created_at": "2026-08-20T07:00:00Z",
      "last_message_at": "2026-08-20T07:14:09Z",
      "last_message_text": "Сообщение очевидца",
      "unread_count": 1
    }
  ],
  "next_before": null
}
```

Ошибки:

- `403` — сотруднику ещё не назначена роль;
- `404` — переданный `device_id` не принадлежит сотруднику.

## GET /api/v1/chats/{chat_id}/messages

Загружает историю сообщений.

```text
GET /api/v1/chats/{chat_id}/messages?requester_device_id={device_id}&limit=50
```

Параметры:

- `requester_device_id` — устройство, которое читает чат;
- `limit` — от 1 до 100, по умолчанию 50;
- `before` — необязательная дата ISO 8601 для загрузки более старых сообщений.

Ответ:

```json
{
  "items": [],
  "next_before": null
}
```

Если `next_before` заполнен, передайте его как `before` в следующем запросе.

## PATCH /api/v1/chats/{chat_id}/messages/{message_id}/read

Отмечает чужое сообщение прочитанным.

```text
PATCH /api/v1/chats/{chat_id}/messages/{message_id}/read?requester_device_id={device_id}
```

Повторный вызов возвращает прежнее время. Отправитель не может отметить собственное сообщение прочитанным.

## WebSocket

Подключение к событиям конкретного чата:

```text
ws://193.124.115.164:4402/api/v1/ws/chats/{chat_id}?device_id={device_id}
```

Backend проверяет доступ устройства к чату. После создания сообщения отправляется событие:

```json
{
  "event": "message.created",
  "data": {
    "id": "42626038-9eb9-4915-acc3-f425e8d575cd",
    "chat_id": "65cb767f-d939-466e-beaf-8334c97f0612",
    "sender_device_id": "0759db59-5263-41c2-a6fc-e16d8cc76f95",
    "sender_type": "witness",
    "message_type": "text",
    "text": "Новое сообщение",
    "sent_at": "2026-08-20T07:14:09Z",
    "read_at": null,
    "deleted": false
  }
}
```

При обрыве сети frontend должен переподключиться и вызвать HTTP-историю, чтобы догрузить пропущенные сообщения.

## POST /api/v1/witnesses/{witness_id}/bans

Выдаёт бан очевидцу.

```json
{
  "issued_by_device_id": "4502a5b0-905d-4160-b4c5-f1b470e0e494",
  "ban_level": 1,
  "reason": "Нарушение правил",
  "expires_at": "2026-08-22T12:00:00+03:00"
}
```

`ban_level`: 1–3. `expires_at` может быть `null` для постоянного бана. Дата должна содержать часовой пояс и находиться в будущем.

Текущая версия разрешает управление банами ролям `administrator` и `chief`.

Ошибки:

- `403` — недостаточно прав;
- `404` — очевидец не найден;
- `409` — уже существует активный бан или дата окончания некорректна.

## GET /api/v1/witnesses/{witness_id}/bans

Возвращает историю банов:

```text
GET /api/v1/witnesses/{witness_id}/bans?requester_device_id={device_id}
```

```json
{
  "items": []
}
```

## PATCH /api/v1/witnesses/{witness_id}/bans/{ban_id}/revoke

Снимает активный бан.

```json
{
  "revoked_by_device_id": "4502a5b0-905d-4160-b4c5-f1b470e0e494",
  "comment": "Бан снят"
}
```

## PUT /api/v1/employees/{employee_id}/role

Назначает или заменяет роль сотрудника.

```json
{
  "requester_device_id": "4502a5b0-905d-4160-b4c5-f1b470e0e494",
  "role": "inspector"
}
```

Роли:

```text
inspector
administrator
chief
```

Администратор назначает `inspector` и `administrator`. Начальник может назначать все роли. Последнюю активную роль `chief` изменить нельзя.

Важно: текущий маршрут принимает `employee_id`, который возвращается при регистрации. Назначение непосредственно по `device_id` из QR-кода ещё не реализовано.

## DELETE /api/v1/employees/{employee_id}/role

Снимает роль:

```text
DELETE /api/v1/employees/{employee_id}/role?requester_device_id={device_id}
```

Последнюю роль `chief` снять нельзя.

## GET /api/v1/employees/{employee_id}/roles/history

Возвращает историю назначений:

```text
GET /api/v1/employees/{employee_id}/roles/history?requester_device_id={device_id}
```

```json
{
  "items": [
    {
      "id": "UUID",
      "employee_id": "UUID",
      "role": "inspector",
      "assigned_by_employee_id": "UUID",
      "assigned_at": "2026-08-20T12:00:00Z",
      "revoked_at": null
    }
  ]
}
```

## Минимальное подключение приложения Очевидца

1. Получить системные параметры устройства.
2. Сформировать SHA-256 fingerprint.
3. Вызвать регистрацию с `type: witness`.
4. Сохранить `device_id`, `witness_id`, `chat_id`.
5. Загрузить историю сообщений.
6. Подключить WebSocket.
7. Отправлять текстовые сообщения через HTTP.
8. После восстановления сети повторно загрузить историю.

Этот сценарий уже можно проверять в тестовом APK через публичный сервер.

## Минимальное подключение приложения Сотрудника

1. Сформировать fingerprint.
2. Зарегистрироваться с `type: employee`.
3. Сохранить `device_id`, `employee_id`, `role`.
4. Устройство без роли пока не имеет доступа к сообщениям.
5. После назначения роли получить список через `GET /api/v1/chats`.
6. Использовать `id` выбранного чата как `chat_id`.
7. Загружать историю и подключать WebSocket.
8. Для администратора и начальника использовать маршруты ролей и банов.

Регистрацию сотрудника, список чатов, роли и сообщения уже можно проверять через публичный сервер.

## Пример Retrofit

```kotlin
interface GibddApi {
    @POST("api/v1/devices/register")
    suspend fun register(@Body body: RegisterRequest): RegisterResponse

    @GET("api/v1/chats")
    suspend fun chats(
        @Query("requester_device_id") deviceId: String,
        @Query("limit") limit: Int = 50
    ): ChatListResponse

    @GET("api/v1/chats/{chatId}/messages")
    suspend fun messages(
        @Path("chatId") chatId: String,
        @Query("requester_device_id") deviceId: String,
        @Query("limit") limit: Int = 50
    ): MessageListResponse
}
```

```kotlin
val retrofit = Retrofit.Builder()
    .baseUrl("http://193.124.115.164:4402/")
    .addConverterFactory(GsonConverterFactory.create())
    .build()
```

## Ещё не реализовано

- access-токены и полноценная авторизация;
- назначение роли напрямую по `device_id` QR-кода;
- ответы сотрудников только предопределёнными шаблонами;
- автоматический срок и автоматическое завершение бана;
- медиафайлы;
- статическая и live-геопозиция;
- push-уведомления и чат уведомлений начальника;
- Excel-отчёты;
- TLS/HTTPS.

Frontend не должен вызывать отсутствующие маршруты до их реализации.

Отсутствие перечисленных функций не мешает тестировать готовую часть приложения: регистрацию, повторный вход, текстовый чат, WebSocket, роли и баны.
