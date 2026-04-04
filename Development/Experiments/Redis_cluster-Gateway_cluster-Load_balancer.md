---
experiment: RedisCluster+GatewayCluster+LoadBalancer
---
> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]]

# Redis
1. Launch the **master**
```bash
sudo docker run -d \
  --name redis-master \
  --network redis-test-net \
  -p 6379:6379 \
  -v $(pwd)/data:/data \
  redis:latest redis-server --appendonly yes --appendfsync always
```

Note the `--appendonly yes` parameter; this tells Redis to use the [[Development/Redis#AOF (Append Only File)]] method.
 
> [!important]
> The previous command must be run from the path that is wanted to contain the `master-server` data.

2. Launch the replica
```bash
sudo docker run -d \
  --name redis-replica \
  --network redis-test-net \
  redis:latest redis-server --replicaof redis-master 6379
```

3. Load the `buy_ticket` function to the **master**, and set its initial state as it was done in the steps 2 and 3 of [[Development/Experiments/Redis-OpenResty#Redis|Redis-OpenResty#Redis]].

## Checks
### Replica instance has also the initial state
Open the `redis-cli` from the **redis-replica** and check that the initial state set to the **master** is also in the replica.
#### Expected
```bash
$ docker exec -it redis-replica redis-cli
127.0.0.1:6379> GET tickets-counter
"20000"
```

## Benchmarks
### AOF persistence with exhaustive *fsync*
Since AOF persistence with *fsync* for each request introduces latency and slows down the system, it must be tested to check whether it now fills our requirements or not.

```bash
docker run --rm \
	--network redis-test-net \
	--cpuset-cpus="1-5" --memory="8g" \
	redis:latest \
	redis-benchmark -h redis-master -c 5 -n 40000 -q --threads 5 -r 20000 \
	fcall buy_ticket 2 purchased_tracking_ids tickets-counter __rand_int__
```

> [!note] 
> This is the same benchmark performed at [[Development/Redis#Benchmark Hotspots]].

#### Results
![[numbered-tickets-hotspots-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-master-replica-BUY-function-V0.1-benchmark.csv]]
```
In conclusion, the Redis server will be fast enough for the dimensions of the given task, but a solution must be given to be able to scale the system to a more demanding scenario.