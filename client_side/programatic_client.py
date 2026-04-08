"""
Simulation of real client, who queues ticket requests reading from a file
into RabbitMQ middleware (using a quorum replicated queue).
Single-threaded version.
"""

import pika
import argparse
import time

RABBITMQ_USER="admin"
RABBITMQ_PASS="admin123"

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

EXCHANGE_NAME='ticket.requests'

start_time: float
end_time: float
connection: pika.adapters.blocking_connection.BlockingConnection
channel: pika.adapters.blocking_connection.BlockingChannel

def client_publisher(lines_list):
    """
    Function executed in the main thread.
    It opens the connection, declares the queues, and publishes all lines.
    """
    # 1. Open the connection to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=rabbitmq_host,
                                           credentials=credentials)
    global connection
    connection = pika.BlockingConnection(parameters)
    global channel
    channel = connection.channel()

    # 2. Declare the Consistent Hash Exchange
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type='x-consistent-hash',
        durable=True
    )

    # 3. Explicitly declare 3 Quorum Queues and bind them to the exchange.
    # The routing_key '1' acts as the weight (meaning all 3 queues receive equal traffic).
    for i in range(1, 4):
        shard_name = f'ticket.shard.{i}'
        channel.queue_declare(
            queue=shard_name,
            durable=True,
            arguments={'x-queue-type': 'quorum',
                       'x-quorum-initial-group-size': 3}
        )
        channel.queue_bind(
            queue=shard_name,
            exchange=EXCHANGE_NAME,
            routing_key='1'
        )

    global start_time
    start_time = time.time()

    # 4. Burst publish the messages
    for index, line in enumerate(lines_list):
        if line.startswith("BUY "):
            # The x-consistent-hash exchange uses this dynamic string to distribute the load
            dynamic_routing_key = str(index)

            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=dynamic_routing_key,
                body=line.encode('utf-8'),
                properties=pika.BasicProperties(
                    delivery_mode=pika.DeliveryMode.Persistent
                )
            )


if __name__ == '__main__':
    source_file = 'benchmarks/benchmark_unnumbered_20000.txt'

    # Read the entire file into main memory
    with open(source_file, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    # Execute the publishing process synchronously
    client_publisher(lines)

    print("Queue flooding completed.")
    print("Checking shards till all tickets are processed.")

    while True:
        total_pending_messages = 0

        # Iterate over the exactly known 3 shard queues
        for i in range(1, 4):
            shard_name = f'ticket.shard.{i}'

            # The passive=True flag checks the queue state without modifying it
            queue_state = channel.queue_declare(queue=shard_name, passive=True)
            total_pending_messages += queue_state.method.message_count

        if total_pending_messages == 0:
            # All shard queues have been fully drained by the workers
            break

        # Wait before checking again to avoid spamming the RabbitMQ server
        time.sleep(1)

    connection.close()

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Benchmark completed.")
    print(f"Total End-to-End time: {total_time:.2f} seconds")