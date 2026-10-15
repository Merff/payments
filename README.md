Асинхронный сервис процессинга платежей. Принимает запросы на оплату, обрабатывает их через эмуляцию платёжного шлюза и уведомляет клиента о результате через webhook.

## Как это работает

```
POST /api/v1/payments
  └─ одна транзакция: payments + outbox
                            │
consumer: outbox relay ─────┘ раз в секунду публикует события в очередь payments.new
consumer: обработчик ←── payments.new
  ├─ эмуляция шлюза: 2–5 сек, 90% succeeded / 10% failed
  ├─ обновление статуса и processed_at
  └─ webhook: 3 попытки с задержкой 1 и 2 сек
        └─ все попытки неудачны → payments.dlx → payments.dlq
```

- **Outbox.** Платёж и событие `payments.new` пишутся в одной транзакции. Consumer забирает неопубликованные события через `FOR UPDATE SKIP LOCKED` и публикует их как persistent-сообщения. Поэтому событие не теряется, даже если RabbitMQ был недоступен.
- **Идемпотентность.** Повторный запрос с тем же `Idempotency-Key` получает тот же ответ `202` с исходным платежом и не создаёт дубль.
- **Повторная доставка.** Outbox гарантирует доставку «хотя бы один раз», поэтому consumer обрабатывает только платежи в статусе `pending`, а повторные сообщения пропускает.
- **DLQ.** Если обработка сообщения упала (вебхук не доставлен после 3 попыток, ошибка базы и т. п.), сообщение отклоняется и через dead-letter exchange `payments.dlx` попадает в очередь `payments.dlq`.

## Запуск в Docker

```bash
make up
```

Поднимаются `postgres`, `rabbitmq`, `api` и `consumer`. Миграции применяются при старте `api`.

- API: http://localhost:8000/health, документация: http://localhost:8000/docs
- RabbitMQ UI: http://localhost:15672 (guest / guest)

Остановить:

```bash
make down
```

## Примеры

Все эндпоинты `/api/v1/payments` требуют заголовок `X-API-Key` (по умолчанию `secret`).

### Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: secret" \
  -H "Idempotency-Key: order-1" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "description": "Order #1",
    "meta": {"order_id": 1},
    "webhook_url": "http://host.docker.internal:8099/webhook"
  }'
```

Ответ `202 Accepted`:

```json
{"payment_id": 1, "status": "pending", "created_at": "2026-10-15T12:58:29.401576"}
```

Повтор с тем же `Idempotency-Key` возвращает тот же ответ `202` с исходным платежом.

`webhook_url` необязателен, но если передан, должен быть `http`/`https` URL, иначе `422`.

### Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/1 -H "X-API-Key: secret"
```

Ответ `200 OK`:

```json
{
  "payment_id": 1,
  "status": "succeeded",
  "created_at": "2026-10-15T12:58:29.401576",
  "amount": "100.50",
  "currency": "RUB",
  "description": "Order #1",
  "meta": {"order_id": 1},
  "webhook_url": "http://host.docker.internal:8099/webhook",
  "processed_at": "2026-10-15T12:58:32.424042"
}
```

### Webhook

После обработки на `webhook_url` уходит `POST` с телом в том же формате, что ответ `GET /api/v1/payments/{payment_id}`. Таймаут запроса — 3 секунды, любой ответ кроме 2xx считается ошибкой.
