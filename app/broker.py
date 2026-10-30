from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.config import settings

broker = RabbitBroker(settings.rabbitmq_url)
dead_letter_exchange = RabbitExchange("payments.dlx", type=ExchangeType.FANOUT, durable=True)
dead_letter_queue = RabbitQueue("payments.dlq", durable=True)
payments_queue = RabbitQueue(
    "payments.new", durable=True, arguments={"x-dead-letter-exchange": dead_letter_exchange.name}
)
retry_queues = [
    RabbitQueue(
        f"payments.retry.{attempt}",
        durable=True,
        arguments={
            "x-message-ttl": delay * 1000,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": payments_queue.name,
        },
    )
    for attempt, delay in enumerate([1, 2], start=1)
]
