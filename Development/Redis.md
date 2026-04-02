---
software: Redis
---
# Numbered tickets
## Logic
Here's how a client (Pyro server) would check if the buy has been successfully made or not:
> [!warning] Initial state
> The database must have no keys created. (you can use `FLUSHALL` to delete every key, **BE CAREFUL IN NON ISOLATED ENVIRONMENTS**)
1. `ticket:number` is valid if `0 <= number < 20000`
2. `SETNX <ticket:number> 1`. The returned value can be:
	- **1** -> If the key didn't already exist => ticket is yours
	- **0** -> If the key did already exist => ticket has been already sold
# Unnumbered tickets
## Logic
> [!warning] Initial state
> The database must have a key called `tickets-counter` initialized to 20.000.

1. `DECR tickets-counter`. The returned value can be:
	- **<= 0** -> The aren't tickets available => purchase failed
	- **> 0** -> There are tickets available => purchase successful

### Exceptions
#### problem:: Client's request timeouts
![[parallel-treat-timeout]]
This is a huge problem that must be solved.
##### solution-to:: [[#problem Client's request timeouts]]
Being able to identify the client that generated the request is crucial for the solution. To avoid login, clients will first request a **tracking ID** that will be linked to its purchase. Then they will send a purchase request; if they need to retry, indicating the same tracking ID will prevent them from purchasing 2 different tickets.

# Fault tolerance
#todo
# Experiments
## Experiment:: Throughput
How much **throughput** Redis supports? The following test has been performed to gather some data.
### Experiment:: Unnumbered tickets
1. Create a **Docker Network** to enable containers communication
```bash
docker network create redis-bench-net
```

2. Launch the Redis server attached to the network (with resource constraints)
```bash
docker run -d \
  --name redis-server \
  --network redis-bench-net \
  --cpuset-cpus="0" \
  --memory="2g" \
  redis:latest
```

3. Run the benchmark in another container (also attached to the network)
The benchmark is configured to send **40.000 requests** simulating **5 connections** that represent the workers of the system. That will be performed for the following operations:
> [!note]
> Note that **40.000 requests** it's double the amount of available seats; this is more accurate to a real scenario.
- `DECR`

```bash
docker run \
--rm --network redis-bench-net \
--cpuset-cpus="1-5" --memory="8g" redis:latest \
redis-benchmark -h redis-server -c 5 -n 40000 -q --threads 5 \
--csv \
DECR tickets-counter
```

#### Results
![[unnumbered-tickets-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-benchmark.csv]]
```
In conclusion and for the given scenario, Redis will not need to be scaled horizontally.

### Experiment:: Numbered tickets
#### Experiment:: No hotspots
In this experiment, no seats are preferred against other, so the probability of a client willing to buy a seat number `x` it's the same than for `y`.
> [!important] Disclaimer
> This differs from reality, therefore, a posterior test will be made to simulate more precisely the reality.

The procedure to perform the test can be reused until the **step 2** of [[#Experiment Unnumbered tickets]], the 3º step would be the following for this case.

```shell
docker run \
--rm --network redis-bench-net \
--cpuset-cpus="1-5" --memory="8g" redis:latest \
redis-benchmark -h redis-server -c 5 -n 40000 -q --threads 5 -r 20000 \
--csv \
SETNX ticket:__rand_int__ 1
```
##### Results
![[numbered-tickets-no-hotspots-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[numbered-tickets-no-hotspots-benchmark.csv]]
```
#### Experiment:: Hotspots
In this experiment, the 80% of the requests will be targeted to a 5% of the seats. To simulate this, the test will execute
- 80% of 40.000 requests = 32.000 requests
- 5% of 20.000 seats = 1000 seats

So the **3º step** command in this case is the following:

```bash
docker run \
--rm --network redis-bench-net \
--cpuset-cpus="1-5" --memory="8g" redis:latest \
redis-benchmark -h redis-server -c 5 -n 32000 -q --threads 5 -r 1000 \
--csv \
SETNX ticket:__rand_int__ 1
```

![[numbered-tickets-hotspots-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[numbered-tickets-hotspots-benchmark.csv]]
```
