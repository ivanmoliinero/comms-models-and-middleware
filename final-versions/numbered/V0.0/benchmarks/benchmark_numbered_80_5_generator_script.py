import random

def generate_benchmark(filename="benchmark_skewed_numbered.txt"):
    requests = []
    request_counter = 1

    # Phase 1: Seats 1 to 19,000 (1 request each)
    for seat_id in range(1, 19001):
        client_id = f"user{request_counter:05d}"
        req_id = f"{request_counter:05d}"
        requests.append(f"BUY {client_id} {seat_id} {req_id}")
        request_counter += 1

    # Phase 2: Seats 19,001 to 20,000 (80 requests each)
    for seat_id in range(19001, 20001):
        for _ in range(80):
            client_id = f"user{request_counter:05d}"
            req_id = f"{request_counter:05d}"
            requests.append(f"BUY {client_id} {seat_id} {req_id}")
            request_counter += 1

    # Shuffle to distribute the hot-key contention evenly across the test duration
    random.shuffle(requests)

    # Write to the file with the specified header
    with open(filename, 'w') as f:
        f.write("# Concert Ticket Benchmark – Numbered Seats\n")
        f.write("# Seats: 1..20000 (1-19000: 1 req/seat, 19001-20000: 80 reqs/seat)\n")
        f.write("# Format: BUY <client_id> <seat_id> <request_id>\n\n")
        
        for req in requests:
            f.write(req + "\n")

    total_requests = len(requests)
    print(f"Successfully generated {total_requests} requests in '{filename}'.")

if __name__ == "__main__":
    generate_benchmark()
