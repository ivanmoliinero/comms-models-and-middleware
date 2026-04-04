import redis
import argparse

# Define the exact keys used in the worker script
START_TIME_KEY = 'start_time'
END_TIME_KEY = 'end_time'
COUNTER_KEY = 'ticket_counter'

# Initialize the argument parser
parser = argparse.ArgumentParser(
    description="Fetch benchmark results from Redis and reset them.")

# Define the argument with 'localhost' as the default fallback value for Redis
parser.add_argument(
    '--redis-host',
    type=str,
    default='localhost',
    help='Host address for Redis'
)

# Parse the command-line arguments
args, unknown = parser.parse_known_args()
redis_host = args.redis_host


def calculate_benchmark_time():
    """
    Connects to Redis, retrieves the start/end timestamps and the counter,
    calculates the elapsed time, and resets all three keys to 0.
    """
    # Establish connection to Redis
    client = redis.Redis(
        host=redis_host,
        port=6379,
        password='admin123',
        decode_responses=True
    )

    # Fetch the string values from Redis
    start_time_str = client.get(START_TIME_KEY)
    end_time_str = client.get(END_TIME_KEY)
    counter_str = client.get(COUNTER_KEY)

    # Validate that the time keys exist
    if not start_time_str or not end_time_str:
        print("Error: The benchmark timestamps are missing in Redis.")
        print(
            "Ensure the worker script has processed the first and last messages.")
        return

    # Convert the string timestamps to floating-point numbers
    start_time = float(start_time_str)
    end_time = float(end_time_str)

    # Handle the counter value
    tickets_processed = int(counter_str) if counter_str else 0

    # Calculate the delta
    total_time = end_time - start_time

    print(f"Benchmark Start Time: {start_time}")
    print(f"Benchmark End Time:   {end_time}")
    print(f"Total tickets processed: {tickets_processed}")
    print(f"Total processing time: {total_time:.4f} seconds")

    # Reset variables to 0 as requested
    client.set(START_TIME_KEY, 0)
    client.set(END_TIME_KEY, 0)
    client.set(COUNTER_KEY, 0)

    print(
        "Variables 'start_time', 'end_time', and 'ticket_counter' have been reset to 0.")


if __name__ == '__main__':
    calculate_benchmark_time()