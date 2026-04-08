---
experiment: RedisShardingSentinel-Gateway
todo: Whole experiment
---
# Brief

In this experiment we will put to the test **self-healing** for the Redis shards.

> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]].

# Redis
To implement **self-healing** in Redis we could use **sentinels**. **Sentinels** monitor the Redis instances, if any is detected as dead, they perform an action in consequence. In this case, the action to be performed is to promote a replica to master.

> [!cite]
> "*At least 3 Sentinel instances are recommended for a robust deployment.*"
> 
> source:: https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/#fundamental-things-to-know-about-sentinel-before-deploying

We will have the following instances running in this experiment:
- 3 masters: master-a, master-b, master-c
- 3 replicas: replica-a, replica-b, replica-c
- 3 sentinels: sentinel-1, sentinel-2, sentinel-3

Since we have a lot to initiate, the following script performs all the setup for Redis in this experiment: [[software-testing/redisShardingSentinel-gatewaysCluster-loadBalancer/redis/deploy.sh]].

## Checks

Apart from the behavior check we will perform, to see the logs it's also interesting. This can be done by executing:

```bash
docker logs -f sentinel-1
```

Looking the *sentinel-1*'s logs it's enough.

We will now **simulate a failover** by pausing a master, in this case, *master-a*.

1. Pause *master-a*.
```bash
docker pause master-a
```

After 3 seconds, the log should show some movements. Precisely, we are looking for
- `+sdown master shard-a 172.19.0.2 6379`
- `+odown master shard-a 172.19.0.2 6379 #quorum 3/2`
- `+switch-master shard-a 172.19.0.2 6379 172.19.0.5 6379`

> [!warning]
> Don't panic if the log keeps printing `+switch-master shard-a 172.19.0.2 6379 172.19.0.5 6379` indefinitely, it is the expected behavior if you **stopped** the container instead of **pausing** it (Docker's DNS reasons).