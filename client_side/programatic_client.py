"""
Simulation of real client, who queues ticket requests reading from a file
into RabbitMQ middleware (using a quorum replicated queue).
Single-threaded version.
"""

import pika
import argparse

RABBITMQ_USER="admin"
RABBITMQ_PASS="admin123"

# Initialize the argument parser
parser = argparse.ArgumentParser(description="RabbitMQ connection script.")

# Define the argument with 'localhost' as the default fallback value
parser.add_argument(
    '--rabbitmq-host',
    type=str,
    default='3.92.204.239',
    help='Host address for RabbitMQ'
)

# Parse the command-line arguments
args, unknown = parser.parse_known_args()

# Obtain RabbitMQ host from the parsed arguments
rabbitmq_host = args.rabbitmq_host

QUEUE_NAME='ticket.requests'
EXCHANGE_NAME='ticket.acquisition'


def client_publisher(lines_list):
    """
    Function executed in the main thread.
    It opens the connection, declares the queue, and publishes all lines.
    """
    # 1. Open the connection to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=rabbitmq_host,
                                           credentials=credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # 2. Declare the quorum queue (idempotent operation)
    channel.exchange_declare(exchange=EXCHANGE_NAME,
                             exchange_type='direct')
    channel.queue_declare(queue=QUEUE_NAME,
                          durable=True,
                          arguments={'x-queue-type': 'quorum'})
    channel.queue_bind(queue=QUEUE_NAME,
                       exchange=EXCHANGE_NAME,
                       routing_key=QUEUE_NAME)

    # 3. Burst publish the messages
    for line in lines_list:
        if line.startswith("BUY "):
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=QUEUE_NAME,
                body=line.encode('utf-8'),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent
                )
            )

    connection.close()


if __name__ == '__main__':
    source_file = 'benchmarks/benchmark_unnumbered_20000.txt'

    # Read the entire file into main memory
    with open(source_file, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    # Execute the publishing process synchronously
    client_publisher(lines)

    print("Queue flooding completed.")