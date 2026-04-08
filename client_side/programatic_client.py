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

    # 2. Declare the quorum queue (idempotent operation)
    channel.exchange_declare(exchange=EXCHANGE_NAME,
                             exchange_type='direct')
    channel.queue_declare(queue=QUEUE_NAME,
                          durable=True)
    channel.queue_bind(queue=QUEUE_NAME,
                       exchange=EXCHANGE_NAME,
                       routing_key=QUEUE_NAME)

    global start_time
    start_time = time.time()

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