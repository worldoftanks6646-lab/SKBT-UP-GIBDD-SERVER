# API «ГИБДД-Очевидец»

Документ предназначен для разработчиков Android-приложений Очевидца и Сотрудника. Он описывает только реализованный API.

## Подключение

Публичный тестовый сервер запущен и доступен по адресу:

```text
https://силенок.рф:4402
```

Состояние на 21 августа 2026 года:

- PostgreSQL подключён, миграции применены;
- FastAPI запущен как служба systemd;
- Nginx принимает внешние запросы на порту `4402`;
- регистрация, повторный вход, создание чата, отправка и получение сообщений проверены через публичный адрес;
- Docker не используется.

Для Retrofit адрес должен заканчиваться `/`:

```kotlin
const val BASE_URL = "https://силенок.рф:4402/"
```

Swagger и OpenAPI:

```text
https://силенок.рф:4402/docs
https://силенок.рф:4402/openapi.json
```

Для Android-приложения добавьте разрешение доступа в интернет в `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

API использует HTTPS, а WebSocket подключается через `wss://`. Разрешать cleartext HTTP в приложении не требуется.

## Общие правила

- запросы и ответы используют JSON;
- UUID передаются строками;
- даты передаются в ISO 8601 с часовым поясом;
- fingerprint создаётся на Android и передаётся как SHA-256 из 64 hex-символов;
- при регистрации frontend сохраняет `device_id`, связанные ID и `access_token` в защищённом хранилище;
- все маршруты, кроме health check и регистрации, требуют заголовок `Authorization: Bearer <access_token>`;
- переданный в запросе `device_id` обязан совпадать с устройством из токена;
- `401` означает отсутствующий/просроченный токен, `403` — недостаточно прав или попытку подмены устройства;
- `400`, `403`, `404`, `409` содержат поле `detail`, а ошибки валидации возвращают `422`.

### Авторизация

`POST /api/v1/devices/register` возвращает токен сроком на 30 дней. Повторная регистрация того же fingerprint выдаёт новый токен. Для Retrofit добавьте interceptor:

```kotlin
request.newBuilder()
    .header("Authorization", "Bearer $accessToken")
    .build()
```

## Реализованные маршруты

```text
GET    /api/health
POST   /api/v1/devices/register

GET    /api/v1/chats
POST   /api/v1/chats/{chat_id}/messages
GET    /api/v1/message-templates
POST   /api/v1/chats/{chat_id}/messages/template
GET    /api/v1/chats/{chat_id}/messages
PATCH  /api/v1/chats/{chat_id}/messages/{message_id}/read
POST   /api/v1/chats/{chat_id}/media
GET    /api/v1/media/{attachment_id}
POST   /api/v1/chats/{chat_id}/locations/static
POST   /api/v1/chats/{chat_id}/locations/live
POST   /api/v1/location-sessions/{session_id}/points
GET    /api/v1/location-sessions/{session_id}
PATCH  /api/v1/location-sessions/{session_id}/finish
GET    /api/v1/notifications
PATCH  /api/v1/notifications/{notification_id}/read
PUT    /api/v1/devices/{device_id}/push-token
DELETE /api/v1/devices/{device_id}/push-token
WS     /api/v1/ws/chats/{chat_id}?token={access_token}

POST   /api/v1/witnesses/{witness_id}/bans
GET    /api/v1/witnesses/{witness_id}/bans
PATCH  /api/v1/witnesses/{witness_id}/bans/{ban_id}/revoke

PUT    /api/v1/employees/{employee_id}/role
PUT    /api/v1/devices/{device_id}/role
DELETE /api/v1/employees/{employee_id}/role
GET    /api/v1/employees/{employee_id}/roles/history
GET    /api/v1/reports/activity.xlsx
```

## GET /api/health

Проверяет доступность backend. Авторизация не нужна.

```bash
curl https://силенок.рф:4402/api/health
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
  "ban_level": 0,
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
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
  "ban_level": null,
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

Первый сотрудник автоматически получает `chief`. Следующие сотрудники создаются без роли.

При повторной регистрации backend возвращает тот же `device_id`, обновляет платформу и версию приложения, а `is_new` становится `false`.

Ошибки:

- `409` — зарегистрированное устройство пытается сменить `type`;
- `422` — fingerprint не состоит ровно из 64 hex-символов или поле заполнено неправильно.

## POST /api/v1/chats/{chat_id}/messages

Создаёт текстовое сообщение очевидца. Сотрудник не может отправлять через этот маршрут произвольный текст и получает `403`.

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

## Шаблоны ответов сотрудников

Сотрудник с активной ролью получает утверждённые варианты ответа:

```text
GET /api/v1/message-templates?requester_device_id={device_id}
```

```json
{
  "items": [
    {
      "id": "10000000-0000-0000-0000-000000000001",
      "code": "accepted",
      "text": "Ваше сообщение принято."
    }
  ]
}
```

Отправка выбранного шаблона:

```text
POST /api/v1/chats/{chat_id}/messages/template
```

```json
{
  "sender_device_id": "UUID сотрудника",
  "template_id": "10000000-0000-0000-0000-000000000001"
}
```

Backend самостоятельно берёт актуальный текст шаблона. Очевидец не может использовать этот маршрут. Неактивный или неизвестный шаблон возвращает `404`.

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

## POST /api/v1/chats/{chat_id}/media

Загружает медиафайл и создаёт сообщение типа `media`. Используется `multipart/form-data`.

Поля формы:

- `sender_device_id` — UUID устройства отправителя;
- `file` — файл JPEG, PNG, GIF, MP4 или MOV размером до 100 МБ.

```bash
curl -X POST "https://силенок.рф:4402/api/v1/chats/{chat_id}/media" \
  -F "sender_device_id={device_id}" \
  -F "file=@photo.jpg;type=image/jpeg"
```

Ответ `201 Created` содержит объект сообщения и вложения:

```json
{
  "message": {
    "id": "UUID",
    "chat_id": "UUID",
    "sender_device_id": "UUID",
    "sender_type": "witness",
    "message_type": "media",
    "text": null,
    "sent_at": "2026-08-23T12:00:00Z",
    "read_at": null,
    "deleted": false,
    "attachment_id": "UUID"
  },
  "attachment": {
    "id": "UUID",
    "message_id": "UUID",
    "media_type": "photo",
    "mime_type": "image/jpeg",
    "original_name": "photo.jpg",
    "size_bytes": 12345,
    "uploaded_at": "2026-08-23T12:00:00Z",
    "expires_at": "2026-08-30T12:00:00Z",
    "download_url": "/api/v1/media/UUID"
  }
}
```

Забаненный очевидец получает `403` и не может загрузить файл. Медиа хранится 7 дней; каждое успешное скачивание продлевает срок ещё на 7 дней.

## GET /api/v1/media/{attachment_id}

Возвращает файл пользователю, имеющему доступ к его чату:

```text
GET /api/v1/media/{attachment_id}?requester_device_id={device_id}
```

В истории сообщений поле `attachment_id` содержит идентификатор файла. Ошибки: `403` при отсутствии доступа, `404` для отсутствующего или просроченного файла.

## WebSocket

Подключение к событиям конкретного чата:

```text
wss://силенок.рф:4402/api/v1/ws/chats/{chat_id}?token={access_token}
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

## Статическая геопозиция

```text
POST /api/v1/chats/{chat_id}/locations/static
```

```json
{
  "sender_device_id": "UUID",
  "latitude": 55.7558,
  "longitude": 37.6176,
  "accuracy": 5.0,
  "captured_at": "2026-08-23T15:00:00+03:00"
}
```

`latitude` должна быть от −90 до 90, `longitude` — от −180 до 180, точность не может быть отрицательной. `captured_at` необязателен; если он передан, часовой пояс обязателен.

Ответ `201` содержит сообщение типа `geolocation`, завершённую сессию типа `static` и одну точку. В истории сообщений идентификатор находится в `location_session_id`.

## Live-геопозиция

Запуск сессии:

```text
POST /api/v1/chats/{chat_id}/locations/live
```

```json
{
  "sender_device_id": "UUID",
  "duration_seconds": 900
}
```

Продолжительность — от 60 до 3600 секунд. Backend возвращает `session.id`. Пока сессия активна, приложение отправляет точку примерно раз в секунду:

```text
POST /api/v1/location-sessions/{session_id}/points
```

```json
{
  "sender_device_id": "UUID",
  "latitude": 55.7558,
  "longitude": 37.6176,
  "accuracy": 5.0,
  "captured_at": "2026-08-23T15:00:01+03:00"
}
```

Точки получают последовательные номера. Добавлять точки и завершать сессию может только устройство, которое её запустило. Забаненный очевидец получает `403`. После достижения `expires_at` новая точка возвращает `409`, а статус меняется на `expired`.

Получение сессии и всех точек:

```text
GET /api/v1/location-sessions/{session_id}?requester_device_id={device_id}
```

Завершение раньше установленного срока:

```text
PATCH /api/v1/location-sessions/{session_id}/finish
```

```json
{
  "sender_device_id": "UUID"
}
```

Через WebSocket участники чата получают событие `message.created` при запуске и `location.point` для каждой новой точки.

## Уведомления сотрудников

Backend автоматически создаёт уведомления всем сотрудникам с активной ролью `chief` при следующих событиях:

- `ban_issued` — очевидцу выдан бан;
- `ban_revoked` — бан снят;
- `role_changed` — сотруднику назначена или изменена роль;
- `role_revoked` — роль снята.

Получение уведомлений текущего сотрудника:

```text
GET /api/v1/notifications?requester_device_id={device_id}&unread_only=false&limit=50
```

Параметры `before` и `limit` используются для пагинации. `unread_only=true` возвращает только непрочитанные записи.

```json
{
  "items": [
    {
      "id": "UUID",
      "type": "ban_issued",
      "related_entity_type": "witness_ban",
      "related_entity_id": "UUID",
      "payload": {
        "witness_id": "UUID",
        "ban_level": 1,
        "reason": "Нарушение правил"
      },
      "is_read": false,
      "created_at": "2026-08-23T15:30:00Z",
      "read_at": null
    }
  ],
  "next_before": null
}
```

Отметка прочитанным:

```text
PATCH /api/v1/notifications/{notification_id}/read
```

```json
{
  "requester_device_id": "UUID"
}
```

Сотрудник может видеть и отмечать только собственные уведомления.

## POST /api/v1/witnesses/{witness_id}/bans

Выдаёт бан очевидцу.

```json
{
  "issued_by_device_id": "4502a5b0-905d-4160-b4c5-f1b470e0e494",
  "reason": "Нарушение правил"
}
```

Уровень и срок backend рассчитывает автоматически по полной истории банов очевидца:

- первый бан — уровень `1`, срок 1 день;
- второй бан — уровень `2`, срок 30 дней;
- третий бан — уровень `3`, бессрочно.

Frontend не должен передавать `ban_level` и `expires_at`.

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

## PUT /api/v1/devices/{device_id}/role — выдача роли по QR

Приложение сотрудника формирует QR-код, содержащий **только строку `device_id`**. ZXing или ML Kit используются на Android; сервер не генерирует изображение QR. Администратор или Начальник сканирует код и отправляет:

```http
PUT /api/v1/devices/{отсканированный_device_id}/role
Authorization: Bearer <токен администратора или начальника>
Content-Type: application/json
```

```json
{
  "requester_device_id": "device_id администратора или начальника",
  "role": "inspector"
}
```

Если устройство не зарегистрировано как `employee`, сервер возвращает `404`. Администратор может назначать `inspector` и `administrator`; роль `chief` может назначать только другой Начальник.

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

## GET /api/v1/reports/activity.xlsx

Начальник выгружает Excel-отчёт за весь период. Требуется Bearer-токен устройства с активной ролью `chief`.

```http
GET /api/v1/reports/activity.xlsx?requester_device_id={device_id}
Authorization: Bearer <access_token>
```

Ответ `200 OK` — файл `gibdd-report.xlsx` с тремя листами:

- `Баны`: дата и время, ID устройства выдавшего бан, ID устройства очевидца;
- `Роли`: дата и время, ID устройства инициатора, выдача/замена/удаление роли, ID целевого устройства;
- `Сообщения`: ID устройства сотрудника и количество отправленных им сообщений.

Отчёт строится по всей истории без ограничения дат. Ошибка `403` возвращается сотруднику без роли Начальника.

Пример Retrofit для получения файла:

```kotlin
@Streaming
@GET("api/v1/reports/activity.xlsx")
suspend fun downloadReport(
    @Query("requester_device_id") deviceId: String
): ResponseBody
```

## Внешние push-уведомления Android (FCM)

После регистрации устройства Android получает FCM token и сохраняет его на backend:

```http
PUT /api/v1/devices/{device_id}/push-token
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "token": "FCM registration token устройства"
}
```

Ответ не возвращает сам токен:

```json
{
  "device_id": "UUID",
  "registered": true,
  "updated_at": "2026-08-25T10:00:00Z"
}
```

FCM может обновить token в любой момент. В `FirebaseMessagingService.onNewToken()` нужно повторно вызвать этот маршрут. При выходе или отключении уведомлений:

```http
DELETE /api/v1/devices/{device_id}/push-token
Authorization: Bearer <access_token>
```

Backend отправляет push:

- всем сотрудникам с активной ролью — при новом тексте, медиа или геопозиции очевидца;
- очевидцу — при шаблонном ответе сотрудника;
- Начальнику — при выдаче/снятии бана и изменении/удалении роли.

В поле `data.event` приходят значения `message.created`, `ban.issued`, `ban.revoked`, `role.changed` или `role.revoked`. Для сообщения также передаются `chat_id`, `message_id` и `message_type`. После push приложение загружает актуальные данные через REST API; содержимое сообщения в push не передаётся.

Минимальная Android-логика:

```kotlin
FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
    // PUT /api/v1/devices/{deviceId}/push-token
}

override fun onNewToken(token: String) {
    // повторно отправить token на backend
}
```

Для Android 13+ требуется разрешение:

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```

Для реальной доставки владелец Firebase-проекта должен положить service-account JSON на сервер вне Git и настроить `PUSH_ENABLED=true`, `FCM_PROJECT_ID` и `FCM_SERVICE_ACCOUNT_FILE`. Без ключа регистрация токенов работает, но отправка в FCM безопасно пропускается.

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
    .baseUrl("https://силенок.рф:4402/")
    .addConverterFactory(GsonConverterFactory.create())
    .build()
```

## Требует внешней настройки

- отправка push через FCM включается после установки service-account JSON владельцем Firebase-проекта;

Frontend не должен вызывать отсутствующие маршруты до их реализации.

Отсутствие перечисленных функций не мешает тестировать готовую часть приложения: регистрацию, повторный вход, текстовый чат, WebSocket, роли и баны.
