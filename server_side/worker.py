"""
Workers of the ticketing system, who obtain the client's requests and
process the tickets according to the source of truth of the
consistency backend.
"""

import pika
import redis
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
parser = argparse.ArgumentParser(description="RabbitMQ and Redis connection script.")

# Define the argument for RabbitMQ expecting a comma-separated list of IPs
parser.add_argument(
    '--rabbitmq-hosts',
    type=str,
    default='localhost',
    help='Comma-separated host addresses for RabbitMQ nodes'
)

# Define the argument with 'localhost' as the default fallback value for Redis
parser.add_argument(
    '--redis-host',
    type=str,
    default='localhost',
    help='Host address for Redis'
)

# Parse the command-line arguments
args, unknown = parser.parse_known_args()

# Obtain hosts from the parsed arguments
rabbitmq_host_list = args.rabbitmq_hosts.split(',')
redis_host = args.redis_host

QUEUE_NAME='ticket.requests'
EXCHANGE_NAME='ticket.acquisition'

# Client redis variable
client: redis.Redis
auto_incr: redis.commands.core.Script


def process_message(ch, method, properties, body):
    """
    Callback function to process incoming messages.
    Manual ACK is strictly enforced here.
    """
    message = body.decode('utf-8')
    print(f"[*] Received: {message}")

    global auto_incr
    result = auto_incr(keys=[COUNTER_VAR, START_TIME_KEY, END_TIME_KEY],
                       args=[MAX_TICKETS])

    # TODO: Where to store metrics of accepted and erased???

    # Explicit manual ACK when op is completed.
    ch.basic_ack(delivery_tag=method.delivery_tag)


def connect_to_redis(host, password, port=6379, delay=5):
    """
    Attempts to connect to Redis infinitely until successful.
    """
    while True:
        try:
            print(f"[*] Attempting to connect to Redis at {host}...")
            r_client = redis.Redis(
                host=host,
                port=port,
                password=password,
                decode_responses=True
            )
            # Ping verifies the connection is actually established
            if r_client.ping():
                print("[*] Successfully connected to Redis.")
                return r_client
        except redis.exceptions.ConnectionError:
            print(f"[!] Redis connection failed. Retrying in {delay} seconds...")
            time.sleep(delay)


def start_worker():
    """
    Initializes the Redis connection, then starts an infinite loop to maintain
    the RabbitMQ connection. If RabbitMQ drops, it catches the error and reconnects.
    """
    global client
    global auto_incr

    # 1. Establish Redis connection with retry mechanism FIRST.
    # We do this outside the RabbitMQ loop so we don't reload Redis on every RMQ drop.
    client = connect_to_redis(redis_host, REDIS_PASS)
    auto_incr = client.register_script(lua_script)

    # 2. Main loop for RabbitMQ connection and consumption
    while True:
        try:
            print(f"[*] Attempting to connect to "
                  f"RabbitMQ")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

            endpoints = []
            # Build the connection parameters for each host in the list
            for rmq_host in rabbitmq_host_list:
                param = pika.ConnectionParameters(
                    host=rmq_host.strip(),
                    credentials=credentials,
                    heartbeat=60,
                    blocked_connection_timeout=300
                )
                endpoints.append(param)

            # Pika will try to connect to endpoints[0], then endpoints[1], etc.
            connection = pika.BlockingConnection(endpoints)
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
            # auto_ack=False is mandatory to prevent automatic deletion of
            # messages.
            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=process_message,
                auto_ack=False
            )

            print(" [*] Worker is ready and waiting for messages. "
                  "To exit press CTRL+C")

            # This is a blocking call. It will stay here as long as the
            # connection is alive.
            channel.start_consuming()

        # Catch connection drops, NLB timeouts, or node failures
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.ConnectionClosedByBroker,
                pika.exceptions.StreamLostError) as error:
            print(f"\n[!] Connection to RabbitMQ lost: {error}")
            print("[*] Waiting 3 seconds before reconnecting...")
            time.sleep(3)
            continue # Restarts the while True loop

        except KeyboardInterrupt:
            print("\n [*] Worker shutdown sequence initiated.")
            if 'connection' in locals() and connection.is_open:
                connection.close()
            break # Exits the while True loop


if __name__ == '__main__':
    start_worker()