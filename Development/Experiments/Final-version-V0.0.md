---
final-version: V0.0
environment: AWS
---
# Description
## Implications of migrating from Docker containers in localhost to AWS

### Instances number limit
Some changes have been done in respect to the most final-version-like experiment ([[Development/Experiments/RedisShardingReplicationSentinel(3+3*2+3)+Gateway|RedisShardingReplicationSentinel(3+3*2+3)+Gateway]]). Such involve reducing the number of instances used by the entire system to 9. This is because this task will be uploaded to AWS, and that is the exact number of instances we are limited to create.
 
To reduce the amount of instances we had been to:
- Reduce the number of shards from 3 to 2, as can be seen at [[#Components].
- Move the Redis Sentinels (3 instances) to live inside the *load balancer* and *gateways*. This is indeed recommended in the following [Redis article](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/#:~:text=The%20three%20Sentinel%20instances%20should%20be%20placed%20into%20computers%20or%20virtual%20machines%20that%20are%20believed%20to%20fail%20in%20an%20independent%20way.%20So%20for%20example%20different%20physical%20servers%20or%20Virtual%20Machines%20executed%20on%20different%20availability%20zones.).

### Docker DNS
Throughout the development, we had been using Docker's DNS to resolve the hardcoded names of the requests' targets. We no longer can rely on this since we won't be keeping all the containers in a Docker network. One possible solution to this is to use the bare IPs.

#further-work Evidently, this should be changed to make the system truly scalable.
## Components

This final version has the following instances:
- 2 Redis shards (that are also sentinels) = (1 master + 2 replicas) per shard * 2 shards = 2 masters + 4 replicas = 6 instances
- 1 load balancer
- 2 gateways in the cluster

# Deploying


# Variants

## variant:: Migrating to a problem-specialized database

One of the conclusions of making this project, is that Redis is not the most suited database for this tasks. Note that we had been disabling all advantages of Redis against other databases throughout the development, such as working at the speeds of RAM and asynchronous replication. This caused the performance of Redis to reduce, maybe to the point where another more problem-specialized database would perform better.