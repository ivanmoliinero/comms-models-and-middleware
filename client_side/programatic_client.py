"""
Simulation of real client, who queues ticket requests reading from a file
into RabbitMQ middleware (using a quorum replicated queue).
"""

import pika
import multiprocessing
import os


QUEUE_NAME='ticket.requests'
EXCHANGE_NAME='ticket.acquisition'


def client_worker_publisher(lines_chunk, local_barrier):
    """
    Function executed by each process.
    It opens its own connection, declares the queue, waits for others,
    and publishes.
    """
    # 1. Each process must open its own connection to RabbitMQ
    # TODO: Replace localhost when using EC2 instances.
    parameters = pika.ConnectionParameters(host='localhost')
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

    # 3. Block the process until all other workers reach this point
    local_barrier.wait()

    # 4. Burst publish the messages
    for line in lines_chunk:
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
    # The client machine should be capable of doing this in order to
    # ensure the most parallel exec possible.
    with open(source_file, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    # Use the number of logical cores available on the machine
    num_processes = 1

    # Create the barrier to synchronize the exact start of the publishing
    barrier = multiprocessing.Barrier(num_processes)

    # Calculate the chunk size for each process
    chunk_size = len(lines) // num_processes

    # Split the lines into smaller lists
    chunks = [lines[i:i + chunk_size] for i in
              range(0, len(lines), chunk_size)]

    processes = []

    # Start the processes
    for chunk in chunks:
        p = multiprocessing.Process(target=client_worker_publisher,
                                    args=(chunk, barrier))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()

    print("Queue flooding completed.")
