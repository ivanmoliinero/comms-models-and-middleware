---
type:
  - database
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

#update 
The [[#problem Client's request timeouts]] provoked a change in the way Redis will treat the request. The solution is studied in here:
![[Excalidraw/unnumbered-tickets-request-lifecycle.md#^frame=KNP3wHsr|V1.0]]

Now every **BUY** must be linked to a **tracking ID**, so a client must first generate a **UUID** locally, and then request the **BUY** operation.

This would be the logic of the **BUY operation**:
![[unnumbered-tickets-request-lifecycle#V0.0 - BUY operation]]

#upgrade
Executing the [[unnumbered-tickets-request-lifecycle#V0.0 - BUY operation]] by means of uploading the script every time is not efficient, the script can be previously uploaded to be stored and managed (and replicated) by Redis, so it can be executed just by calling it.

- **Upload:**
```redis-cli
FUNCTION LOAD 
"
#!lua name=ticket_sales\nredis.register_function(
	'buy_ticket',
	function(keys, args)\n
		if redis.call('SISMEMBER', keys[1], args[1]) == 1 then\n
			return -1\n
		elseif tonumber(redis.call('GET', keys[2])) <= 0 then\n
			return -2\n
		else\n    
			redis.call('SADD', keys[1], args[1])\n
		return redis.call('DECR', keys[2])\n  end\nend)
"
```

- **Call:**
```redis-cli
FCALL buy_ticket 2 purchased_tracking_ids tickets-counter "uuid-test-001"
```

#upgrade 
The [[unnumbered-tickets-request-lifecycle#V0.0 - BUY operation]] could be optimized the following way:
![[unnumbered-tickets-request-lifecycle#V0.1 - BUY operation]]

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

### Experiment:: Unnumbered tickets - [[unnumbered-tickets-request-lifecycle#V0.1 - BUY operation]]

1. Load the function to benchmark
```redis-cli
FUNCTION LOAD REPLACE "#!lua name=ticket_sales\nredis.register_function('buy_ticket', function(keys, args)\n  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then\n    return -1\n  else\n    local ticket_number = tonumber(redis.call('DECR', keys[2]))\n    if ticket_number < 0 then\n      return -2\n    else\n      redis.call('SADD', keys[1], args[1])\n      return ticket_number\n    end\n  end\nend)"
```

2. Reset the state of the database
```redis-cli
DEL purchased_tracking_ids
SET tickets-counter 20000
```

3. Execute the benchmark
```bash
docker run --rm --network redis-bench-net \
--cpuset-cpus="1-5" --memory="8g" redis:latest \
redis-benchmark -h redis-server-test -c 5 -n 40000 -q --threads 5 -r 1000000 \
fcall buy_ticket 2 purchased_tracking_ids tickets-counter __rand_int__
```

Note the value of the `-r` parameter is 1.000.000. This is because we will now indicate the ID of the client requesting the BUY operation through the `__rand_int__` string, and for this test we don't want retries to be performed. (the bigger the key space len, the smaller the probability of a client performing the operation more than one time).

![[unnumbered-tickets-BUY-function-V0.1-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-BUY-function-V0.1-benchmark.csv]]
```
An extra benchmark has been performed to evaluate the performance under heavy loads of clients retries:
```bash
docker run --rm --network redis-bench-net \
--cpuset-cpus="1-5" --memory="8g" redis:latest \
redis-benchmark -h redis-server-test -c 5 -n 40000 -q --threads 5 -r 20000 \
fcall buy_ticket 2 purchased_tracking_ids tickets-counter __rand_int__
```

Since the value of `-r` is now half the number of requests to be performed, at least 20000 retries will be made.

![[unnumbered-tickets-BUY-function-V0.1-retries-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-BUY-function-V0.1-retries-benchmark.csv]]
```
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
