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

# Define the argument with 'localhost' as the default fallback value for RabbitMQ
parser.add_argument(
    '--rabbitmq-host',
    type=str,
    default='localhost',
    help='Host address for RabbitMQ'
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
rabbitmq_host = args.rabbitmq_host
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
                  f"RabbitMQ at {rabbitmq_host}...")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

            # heartbeat ensures the connection is kept alive behind the NLB
            parameters = pika.ConnectionParameters(
                host=rabbitmq_host,
                credentials=credentials,
                heartbeat=60,
                blocked_connection_timeout=300
            )

            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            # We do not declare a specific queue here.
            # The Sharding Plugin manages pseudo-queues automatically.
            # We only need to ensure we consume from the shard-aware exchange.

            # In Sharding, the "queue" is actually a virtual exchange.
            # We MUST declare it as an exchange of type 'x-modulus-hash' so
            # the plugin can intercept it, apply your policy, and create the
            # backing quorum shards.
            channel.exchange_declare(
                exchange=QUEUE_NAME,
                exchange_type='x-modulus-hash',
                durable=True
            )

            # Only 1 message at a time per worker.
            channel.basic_qos(prefetch_count=1)

            # In Sharding, we consume from the exchange name directly,
            # and the plugin routes a specific shard to this consumer.
            channel.basic_consume(
                queue='ticket.requests',  # The plugin makes this name virtual
                on_message_callback=process_message,
                auto_ack=False
            )

            print(" [*] Sharded Worker is ready. Processing local shards...")
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