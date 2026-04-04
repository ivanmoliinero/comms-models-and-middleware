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

QUEUE_NAME='ticket.requests'
EXCHANGE_NAME='ticket.acquisition'

start_time: float
end_time: float
connection: pika.adapters.blocking_connection.BlockingConnection
channel: pika.adapters.blocking_connection.BlockingChannel

def client_publisher(lines_list):
    """
    Function executed in the main thread.
    It opens the connection, declares the queue, and publishes all lines.
    """
    # 1. Open the connection to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=rabbitmq_host,
                                           credentials=credentials)
    global connection
    connection = pika.BlockingConnection(parameters)
    global channel
    channel = connection.channel()

    # 2. Declare the sharded exchange (idempotent operation)
    # The sharding plugin takes over and creates the backing quorum queues automatically.
    # We no longer declare queues or bind them manually.
    channel.exchange_declare(
        exchange=QUEUE_NAME,
        exchange_type='x-modulus-hash',
        durable=True
    )

    global start_time
    start_time = time.time()

    # 3. Burst publish the messages
    # We use 'enumerate' to get an incremental index for each message
    for index, line in enumerate(lines_list):
        if line.startswith("BUY "):
            # CRITICAL: A dynamic routing key is strictly required for the sharding plugin.
            # The x-modulus-hash exchange hashes this key to distribute the load.
            # Using the loop 'index' as a string ensures perfect, even distribution
            # across all 3 RabbitMQ nodes.
            dynamic_routing_key = str(index)

            # Publish directly to the sharded exchange, which shares the name with the logical queue
            channel.basic_publish(
                exchange=QUEUE_NAME,
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
    print("Checking queue till all tickets are processed.")

    while True:
        # The passive=True flag checks the queue state without re-declaring it
        queue_state = channel.queue_declare(queue=QUEUE_NAME, passive=True)
        current_message_count = queue_state.method.message_count

        if current_message_count == 0:
            # The queue has been fully drained by the workers
            break

        # Wait before checking again to avoid spamming the RabbitMQ server
        time.sleep(1)

    connection.close()

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Benchmark completed.")
    print(f"Total End-to-End time: {total_time:.2f} seconds")