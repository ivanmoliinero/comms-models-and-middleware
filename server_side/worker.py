"""
Workers of the ticketing system, who obtain the client's requests and
process the tickets according to the source of truth of the
consistency backend.
"""

import pika
import redis
from redis.sentinel import Sentinel
import argparse
import time

# This script ensures atomic seat reservation and measures total time of processing.
lua_script = '''
-- KEYS[1] = seat_key
-- KEYS[2] = counter_key
-- KEYS[3] = start_time_key
-- KEYS[4] = end_time_key
-- KEYS[5] = failed_counter_key
-- ARGV[1] = client_id
-- ARGV[2] = max_value

-- SETNX returns 1 if the key was set (seat available), 0 if it already existed.
local seat_assigned = redis.call('SETNX', KEYS[1], ARGV[1])

if seat_assigned == 1 then
    -- Seat successfully assigned, increment the global counter of sold tickets
    local current_value = redis.call('INCR', KEYS[2])
    local max_value = tonumber(ARGV[2])

    -- If this is the absolute first successful reservation, record the start time
    if current_value == 1 then
        local server_time = redis.call('TIME')
        local timestamp_str = server_time[1] .. '.' .. server_time[2]
        redis.call('SET', KEYS[3], timestamp_str)
    end

    -- If this increment hits the max limit, record the end time
    if current_value == max_value then
        local server_time = redis.call('TIME')
        local timestamp_str = server_time[1] .. '.' .. server_time[2]
        redis.call('SET', KEYS[4], timestamp_str)
    end
    
    return 1 -- Success
else
    -- Seat already taken, increment the failed attempts counter
    redis.call('INCR', KEYS[5])
    return 0 -- Failed: Seat already taken
end
'''

RABBITMQ_USER="admin"
RABBITMQ_PASS="admin123"
REDIS_PASS="admin123"
MAX_TICKETS=20000
COUNTER_VAR='ticket_counter'
START_TIME_KEY='start_time'
END_TIME_KEY='end_time'

# Initialize the argument parser
parser = argparse.ArgumentParser(description="RabbitMQ and Redis Sentinel connection script.")

parser.add_argument(
    '--rabbitmq-host',
    type=str,
    default='localhost',
    help='Host address for RabbitMQ'
)

# Modified to accept a comma-separated list of Sentinel IPs
parser.add_argument(
    '--redis-sentinels',
    type=str,
    default='localhost',
    help='Comma-separated host addresses for Redis Sentinels'
)

# Parse the command-line arguments
args, unknown = parser.parse_known_args()

rabbitmq_host = args.rabbitmq_host
# Parse the string into a list of tuples: [('IP1', 26379), ('IP2', 26379), ...]
sentinel_hosts = [(ip.strip(), 26379) for ip in args.redis_sentinels.split(',')]

QUEUE_NAME='ticket.requests'
EXCHANGE_NAME='ticket.acquisition'

# Client redis variable
client: redis.Redis
auto_incr: redis.commands.core.Script


def process_message(ch, method, properties, body):
    """
    Callback function to process incoming messages.
    Parses the BUY command, executes the Lua script for atomic reservation,
    and ensures synchronous replication to at least one Redis replica using WAIT.
    """
    message = body.decode('utf-8')
    print(f"[*] Received: {message}")

    # Parse the message format: BUY <client_id> <seat_id> <request_id>
    parts = message.strip().split(' ')
    if len(parts) != 4 or parts[0] != 'BUY':
        print("[!] Invalid message format. Discarding.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    action, client_id, seat_id, request_id = parts
    seat_key = f"seat:{seat_id}"

    global auto_incr
    global client  # Required to invoke the wait command on the active connection

    try:
        # Acquire an exclusive connection from the pool to guarantee sequence.
        # transaction=False ensures we do not wrap this in a MULTI/EXEC block,
        # which allows WAIT to function properly immediately after the script.
        pipeline = client.pipeline(transaction=False)

        # Execute the Lua script through the pipeline object
        auto_incr(
            keys=[seat_key, COUNTER_VAR, START_TIME_KEY, END_TIME_KEY,
                  'failed_counter'],
            args=[client_id, MAX_TICKETS],
            client=pipeline
        )

        # Queue the WAIT command on the exact same physical TCP connection
        pipeline.wait(1, 1000)

        # Execute both commands sequentially and retrieve their respective outputs
        results = pipeline.execute()

        # results[0] corresponds to the Lua script return value (1 or 0)
        # results[1] corresponds to the WAIT command return value
        script_result = results[0]
        replicas_acknowledged = results[1]

        # Validate if the synchronous replication was successful
        if replicas_acknowledged >= 1:
            if script_result == 1:
                print(
                    f"[*] SUCCESS: Seat {seat_id} reserved for Client {client_id}.")
            else:
                print(f"[*] REJECTED: Seat {seat_id} was already taken.")

            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            print(
                "[!] WAIT command timed out: 0 replicas acknowledged the write.")
            print("[*] NACKing message to ensure strict data consistency...")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(1)

    except redis.exceptions.RedisError as e:
        # This catches ConnectionError, ReadOnlyError, and ResponseError (NOQUORUM).
        print(f"[!] Redis execution failed: {e}")
        print("[*] NACKing message to prevent data loss. Requeueing...")

        # NACK the message so RabbitMQ puts it back in the queue.
        # It will be safely redelivered.
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        # Brief pause to prevent a tight loop if the master is temporarily down
        time.sleep(1)


def connect_to_redis_sentinel(sentinel_list, password, delay=5):
    """
    Attempts to connect to the Redis Sentinel cluster and fetch the master.
    """
    while True:
        try:
            print(f"[*] Attempting to connect to Redis Sentinels at {sentinel_list}...")

            # Initialize the Sentinel object
            # We omit sentinel_kwargs={'password': password} because our Sentinel
            # processes do not require authentication on port 26379.
            sentinel_manager = Sentinel(sentinel_list)

            # master_for returns a dynamic client connected to the current master
            r_client = sentinel_manager.master_for(
                'mymaster',
                password=password,
                decode_responses=True
            )

            # Ping verifies the connection to the actual Master is established
            if r_client.ping():
                print("[*] Successfully connected to Redis Master via Sentinel.")
                return r_client

        except (redis.exceptions.ConnectionError, redis.sentinel.MasterNotFoundError) as e:
            print(f"[!] Redis Sentinel connection failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)


def start_worker():
    """
    Initializes the Redis connection, then starts an infinite loop to maintain
    the RabbitMQ connection. If RabbitMQ drops, it catches the error and reconnects.
    """
    global client
    global auto_incr

    # 1. Establish Redis connection using Sentinel
    client = connect_to_redis_sentinel(sentinel_hosts, REDIS_PASS)
    auto_incr = client.register_script(lua_script)

    # 2. Main loop for RabbitMQ connection and consumption
    while True:
        try:
            print(f"[*] Attempting to connect to RabbitMQ at {rabbitmq_host}...")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

            parameters = pika.ConnectionParameters(
                host=rabbitmq_host,
                credentials=credentials,
                heartbeat=60,
                blocked_connection_timeout=300
            )

            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True,
                arguments={'x-queue-type': 'quorum'}
            )

            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=process_message,
                auto_ack=False
            )

            print(" [*] Worker is ready and waiting for messages. To exit press CTRL+C")

            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.ConnectionClosedByBroker,
                pika.exceptions.StreamLostError) as error:
            print(f"\n[!] Connection to RabbitMQ lost: {error}")
            print("[*] Waiting 3 seconds before reconnecting...")
            time.sleep(3)
            continue

        except KeyboardInterrupt:
            print("\n [*] Worker shutdown sequence initiated.")
            if 'connection' in locals() and connection.is_open:
                connection.close()
            break


if __name__ == '__main__':
    start_worker()