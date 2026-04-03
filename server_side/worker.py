"""
Workers of the ticketing system, who obtain the client's requests and
process the tickets according to the source of truth of the
consistency backend.
TODO: As of now, redis/db is not used, integrate later.
"""

import pika
import argparse

# Initialize the argument parser
parser = argparse.ArgumentParser(description="RabbitMQ connection script.")

# Define the argument with 'localhost' as the default fallback value
parser.add_argument(
    '--rabbitmq-host',
    type=str,
    default='localhost',
    help='Host address for RabbitMQ'
)

# Parse the command-line arguments
args, unknown = parser.parse_known_args()

# Obtain RabbitMQ host from the parsed arguments
rabbitmq_host = args.rabbitmq_host

QUEUE_NAME='ticket.requests'
EXCHANGE_NAME='ticket.acquisition'
counter=0


def process_message(ch, method, properties, body):
    """
    Callback function to process incoming messages.
    Manual ACK is strictly enforced here.
    """
    message = body.decode('utf-8')
    print(f"[*] Received: {message}")

    # Simulate processing time.
    # The Redis connection and data handling logic will go here.
    # TODO: INCLUDE REAL PROCESSING WITH BACKEND!!!
    global counter
    counter += 1
    #time.sleep(0.1)

    print(f"[*] Successfully processed request. Total processed: {counter}")

    # Explicit manual ACK.
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_worker():
    """
    Initializes the RabbitMQ connection and starts the consumption loop.
    """
    parameters = pika.ConnectionParameters(host=rabbitmq_host)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Ensure the queue exists (this operation is idempotent)
    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
        arguments={'x-queue-type': 'quorum'}
    )

    # basic_qos guarantees that RabbitMQ will not assign more than 1
    # message to this worker at a time until the previous one is ACKed.
    channel.basic_qos(prefetch_count=1)

    # Register the consumer.
    # auto_ack=False is mandatory to prevent automatic deletion of messages.
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_message,
        auto_ack=False
    )

    print(
        " [*] Worker is ready and waiting for messages. To exit press CTRL+C")

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n [*] Worker shutdown sequence initiated.")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == '__main__':
    start_worker()