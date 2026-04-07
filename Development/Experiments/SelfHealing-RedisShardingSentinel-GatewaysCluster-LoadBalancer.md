---
experiment: SelfHealing-RedisShardingSentinel-GatewaysCluster-LoadBalancer
---
# Brief

In this experiment we will put to the test **self-healing** to every component.

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

