"""
Workers of the ticketing system, who obtain the client's requests and
process the tickets according to the source of truth of the
consistency backend.
"""

import pika
import redis
import argparse
import time
import random
import requests
from requests.auth import HTTPBasicAuth

# This script ensures consistency while measuring total time of processing.
lua_script = '''
-- KEYS[1] = counter_key
-- KEYS[2] = start_time_key
-- KEYS[3] = end_time_key
-- ARGV[1] = max_value

local current_value = tonumber(redis.call('GET', KEYS[1]) or '0')
local max_value = tonumber(ARGV[1])

if current_value == 0 then
    local server_time = redis.call('TIME')
    local timestamp_str = server_time[1] .. '.' .. server_time[2]
    redis.call('SET', KEYS[2], timestamp_str)
end

if current_value < max_value then
    local new_val = redis.call('INCR', KEYS[1])
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
EXCHANGE_NAME='ticket.requests'

parser = argparse.ArgumentParser(description="RabbitMQ and Redis connection script.")
parser.add_argument('--rabbitmq-hosts', type=str, default='localhost', help='Comma-separated IPs')
parser.add_argument('--redis-host', type=str, default='localhost', help='Redis IP')
args, unknown = parser.parse_known_args()

rabbitmq_host_list = args.rabbitmq_hosts.split(',')
redis_host = args.redis_host

client: redis.Redis
auto_incr: any

def process_message(ch, method, properties, body):
    message = body.decode('utf-8')
    print(f"[*] Received: {message}")
    global auto_incr
    auto_incr(keys=[COUNTER_VAR, START_TIME_KEY, END_TIME_KEY], args=[MAX_TICKETS])
    ch.basic_ack(delivery_tag=method.delivery_tag)

def connect_to_redis(host, password, port=6379, delay=5):
    while True:
        try:
            r_client = redis.Redis(host=host, port=port, password=password, decode_responses=True)
            if r_client.ping(): return r_client
        except redis.exceptions.ConnectionError:
            time.sleep(delay)

def get_local_shard_queues(host_ip):
    """
    Queries the RabbitMQ API to find all quorum queues starting with 'ticket.shard.'
    that currently have their Raft Leader running on this specific host_ip.
    """
    local_queues = []
    api_url = f"http://{host_ip}:15672/api/queues/%2F"
    try:
        response = requests.get(
            api_url,
            auth=HTTPBasicAuth(RABBITMQ_USER, RABBITMQ_PASS),
            timeout=3
        )
        if response.status_code == 200:
            queues = response.json()
            for q in queues:
                if q.get("name", "").startswith("ticket.shard."):
                    node_str = q.get("node", "")
                    if "ip-" in node_str:
                        leader_ip = node_str.split("ip-")[1].replace("-", ".")
                        if leader_ip == host_ip:
                            local_queues.append(q["name"])
    except requests.exceptions.RequestException:
        pass
    return local_queues

def declare_topology_across_cluster(hosts):
    """
    Connects to each RabbitMQ node individually to declare its specific shard.
    By default, RabbitMQ places a quorum queue leader on the client-connected node.
    This guarantees perfectly distributed queue leaders across the cluster.
    """
    sorted_hosts = sorted([h.strip() for h in hosts])

    for index, host in enumerate(sorted_hosts):
        shard_name = f'ticket.shard.{index + 1}'
        try:
            print(f"[*] Initializing topology: Declaring {shard_name} on host {host}...")
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(host=host, credentials=credentials, blocked_connection_timeout=5)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type='x-consistent-hash',
                durable=True
            )

            channel.queue_declare(
                queue=shard_name,
                durable=True,
                arguments={'x-queue-type': 'quorum'}
            )

            channel.queue_bind(
                queue=shard_name,
                exchange=EXCHANGE_NAME,
                routing_key='1'
            )

            connection.close()
        except Exception as e:
            print(f"[!] Warning: Could not initialize shard on {host}: {e}")

def start_worker():
    global client
    global auto_incr

    client = connect_to_redis(redis_host, REDIS_PASS)
    auto_incr = client.register_script(lua_script)

    # Introduce jitter to prevent connection storms when dozens of workers start simultaneously
    time.sleep(random.uniform(2.0, 5.0))

    # Explicitly enforce distributed queue placement before anyone starts consuming
    declare_topology_across_cluster(rabbitmq_host_list)
    time.sleep(1) # Give Raft a moment to elect leaders before querying the HTTP API

    while True:
        try:
            random.shuffle(rabbitmq_host_list)
            target_host = rabbitmq_host_list[0].strip()
            print(f"\n[*] Connecting directly to RabbitMQ at {target_host}...")

            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=target_host,
                credentials=credentials,
                heartbeat=60,
                blocked_connection_timeout=300
            )

            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.basic_qos(prefetch_count=1)

            local_shards = get_local_shard_queues(target_host)

            if not local_shards:
                print("[!] This node does not currently lead any shards. Reconnecting elsewhere...")
                connection.close()
                time.sleep(3)
                continue

            for shard_queue in local_shards:
                print(f"[*] Registering consumer for local replicated shard: {shard_queue}")
                channel.basic_consume(
                    queue=shard_queue,
                    on_message_callback=process_message,
                    auto_ack=False
                )

            print(" [*] Worker is fully operational. To exit press CTRL+C")
            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.ConnectionClosedByBroker,
                pika.exceptions.StreamLostError) as error:
            print(f"\n[!] Connection lost: {error}")
            print("[*] Shards will trigger a Raft election. Reconnecting in 3 seconds...")
            time.sleep(3)
            continue

        except KeyboardInterrupt:
            if 'connection' in locals() and connection.is_open:
                connection.close()
            break

if __name__ == '__main__':
    start_worker()