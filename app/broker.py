from faststream.rabbit import RabbitBroker, RabbitQueue

from app.config import settings

broker = RabbitBroker(settings.rabbitmq_url)
payments_queue = RabbitQueue("payments.new", durable=True)
