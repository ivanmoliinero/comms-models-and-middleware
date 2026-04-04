"""
Workers of the ticketing system, who obtain the client's requests and
process the tickets according to the source of truth of the
consistency backend.
"""

import pika
import redis
import argparse

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

# client redis variable
client: redis.Redis
auto_incr: redis.commands.core.Script


def process_message(ch, method, properties, body):
    """
    Callback function to process incoming messages.
    Manual ACK is strictly enforced here.
    """
    message = body.decode('utf-8')
    print(f"[*] Received: {message}")

    # Simulate processing time.
    # The Redis connection and data handling logic will go here.
    global auto_incr
    result = auto_incr(keys=[COUNTER_VAR, START_TIME_KEY, END_TIME_KEY],
                       args=[MAX_TICKETS])

    # TODO: Where to store metrics of accepted and erased???

    # Explicit manual ACK when op is completed.
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_worker():
    """
    Initializes the RabbitMQ and Redis connection and starts the consumption
    loop.
    """
    # RABBITMQ CONNECTION
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=rabbitmq_host,
                                           credentials=credentials)
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

    # Redis connection
    global client
    client = redis.Redis(
        host=redis_host,
        port=6379,
        password=REDIS_PASS,
        decode_responses=True
    )

    global auto_incr
    auto_incr = client.register_script(lua_script)

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