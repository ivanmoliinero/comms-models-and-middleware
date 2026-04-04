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
