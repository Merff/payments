from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.config import settings

broker = RabbitBroker(settings.rabbitmq_url)
dead_letter_exchange = RabbitExchange("payments.dlx", type=ExchangeType.FANOUT, durable=True)
dead_letter_queue = RabbitQueue("payments.dlq", durable=True)
payments_queue = RabbitQueue(
    "payments.new", durable=True, arguments={"x-dead-letter-exchange": dead_letter_exchange.name}
)
