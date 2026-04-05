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

# This script ensures consistency while measuring total time of processing.
lua_script = '''
-- KEYS[1] = counter_key
-- KEYS[2] = start_time_key
-- KEYS[3] = end_time_key
-- ARGV[1] = max_value

local current_value = tonumber(redis.call('GET', KEYS[1]) or '0')
local max_value = tonumber(ARGV[1])

-- If this is the absolute first message being processed, record the start time
if current_value == 0 then
    -- TIME returns an array: [unix_seconds, microseconds]
    local server_time = redis.call('TIME')
    local timestamp_str = server_time[1] .. '.' .. server_time[2]
    redis.call('SET', KEYS[2], timestamp_str)
end

if current_value < max_value then
    local new_val = redis.call('INCR', KEYS[1])
    
    -- If this increment hits the max limit, record the end time
    if new_val == max_value then
        local server_time = redis.call('TIME')
        local timestamp_str = server_time[1] .. '.' .. server_time[2]
        redis.call('SET', KEYS[3], timestamp_str)
    end
    
    return new_val
else
    return -1
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
    Includes fail-safe logic for Redis partitions.
    """
    message = body.decode('utf-8')
    print(f"[*] Received: {message}")

    global auto_incr
    try:
        # The sentinel-managed client automatically discovers the new master
        # if a failover occurred before this call.
        result = auto_incr(keys=[COUNTER_VAR, START_TIME_KEY, END_TIME_KEY],
                           args=[MAX_TICKETS])

        # Explicit manual ACK when Redis operation is successfully completed.
        ch.basic_ack(delivery_tag=method.delivery_tag)

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
            # Provide the password to authenticate with the sentinels themselves
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
            print(f"[*] Attempting to connect to "
                  f"RabbitMQ at {rabbitmq_host}...")
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

            print(" [*] Worker is ready and waiting for messages. "
                  "To exit press CTRL+C")

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