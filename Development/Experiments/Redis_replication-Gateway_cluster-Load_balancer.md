---
experiment: RedisReplication+GatewayCluster+LoadBalancer
---
> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]].

# Redis
1. Launch the **master**
```bash
sudo docker run -d \
  --name redis-master \
  --network redis-test-net \
  -p 6379:6379 \
  -v $(pwd)/container-data:/data \
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

> [!fail] Problem
> #problem With the actual setup, scalability and throughput isn't improved by adding a replica, because the main type of operations is WRITE (such as DECR, SADD). Furthermore, the *replica* will not always be consistent with the data in the *master*; in the case where the **master crashes** but the *replica* does not receive the last operation (due to a network failure for example), the actual **asynchronous replication** would cause such data to be lost until the **master** is recovered.
> 
> So there are in reality 2 problems here:
> - [problem:: Lack of scalability]
> - [problem:: Lack of consistency]

> [!fail] Problem
> [problem:: Fault tolerance]
> With this schema, fault tolerance it's not yet implemented; if the **master crashes**, the gateways would just keep sending requests to the same fallen master. Furthermore, the replica would not even take over the role master because we nowhere added instructions to do it.

[solution-to:: Lack of scalability]
The reality is that *writes* throughput cannot be increased by any replication method by itself; the key where all the operations concentrate is the `tickets-counter` (this is called a **hotspot**). It makes no sense to split (**shard**) a single key among different instances. ^4104cb

The proposed solution is to **split logically** the key, e.g. if `tickets-counter` managed 20.000 tickets, now we split it into `tickets-counter-0` and `tickets-counter-1`, where each one will manage 10.000 tickets. Because of that, we can now create as many independent master instances as needed.

The **separation** of the counter introduces a new possible undesired situation: A node (Redis) fails with 10.000 tickets remaining, the other two nodes in the system (with also 10.000 tickets remaining) sell 7.500 tickets each one until the failed node recovers; now the system is extremely unbalanced, the recovered node would handle all the traffic because the other nodes would run out of tickets before the failed one. Furthermore, if the failed node never recovers, 10.000 tickets wouldn't be sold. Two possible solutions to tackle this situations could be (a combination of both is also valid):
- **Distribution of the remaining tickets**: When a node recovers, the tickets remaining on it are distributed across the others (keeping itself an equal portion), thus, balancing the nodes.
- **Intelligent load balancing**: The load balancer sends the requests to the server with the most tickets remaining. Since we don't want the Redis node's cpu time to be spent on load balancer's queries to know who to deliver the BUY operations, we could just refresh it at intervals (for example of 1 second)
#further-work These two propositions introduce a lot of complexity to the system, so for the first versions of this project they will not be implemented.

The logical separation introduces another undesired situation: The *client-1*'s first purchase goes to the *redis-server-1* and there are tickets available, *redis-server-1* will perform SADD of its tracking ID. If this tracking ID isn't added to every redis server, a second request from the *client-1* with the same tracking ID could be performed; if this second request ends in the *redis-server-2* where the tracking ID is not known, and tickets are yet available, the same tracking ID would have caused 2 sells, which is an strict situation we've defined to not be allowed. This could be solved the following ways:
- Using **asynchronous replication** of the *set* that keeps the IDs among all the masters => This would cause an incredible amount of network traffic as the system grew, so its not suitable for scalability.
- #decision Using **consistent routing routing**: If the *client-1* is always treated by the *redis-server-1* **first**, this situation would be avoided. What it means by "*being treated first*" by *redis-server-1* means that if such server runs out of tickets, clients routed to this server must be able to buy from another redis-server, so after a buy operation returns a *"sold out*" code, the gateway that initiated the request must try with a second redis-server, and so on. #tradeoff Despite this solution **increases the load** of the gateways and the **latency** due to the fact that some purchases may execute a BUY operation to each redis-server to be able to buy, this is the best solution found. #tradeoff Another important consequence is that the total order of the first BUY operation of each client may not be respected since one client could be luckier than other if the load balancer redirects him to a *plenty of tickets* server rather than a *sold-out* one. In this case, even if the unlucky client sent the request first, he may not get a ticket due to the increased latency to get to the *available-yet* server, contrary to the other lucky client. #improvement #further-work The **latency** problem could be reduced by **caching** whether a redis-server has run out of tickets or not, so the gateways don't even try to buy on those.

[solution-to:: Fault tolerance]
#decision Since [[#^4104cb]] we have a **sharded** database system. To introduce fault tolerance, we could add **master-replica** to each shard (this is already a broadly used architecture). A **sentinel** would monitor each node, making a *replica* quickly take over its *master* if it fails, ensuring availability, but this introduces an undesired situation when using **asynchronous replication** that is the default method. This is solved in the [[#^ac5a42|solution to lack of consistency]] 
^6d5c28

[solution-to:: Lack of consistency]
Since [[#^4104cb]] has caused the nodes' data to be disjoint, consistency problems caused by asynchronous replication wouldn't have appeared if the [[#^6d5c28|solution to fault tolerance]] wouldn't have introduced the **master-replica** architecture. There is now a situation where consistency fails:
What if an operation were successfully stored in disk (in the master), acknowledged to the client, but a random network error stopped the operation from reaching the replica. In this moment, if the master crashed before being able to resend it, the replica would be promoted to master with one more ticket than the truly available because it didn't receive the last update, consequently selling more than the available.
A **possible solution** to this situation is to use **synchronous replication**, which in Redis can be approximately implemented using the `WAIT` command. The problem is that it cannot be executed within a LUA function as usual because it would block the execution, it would just return ASAP number of instances that acknowledged the operation, but since we would execute it immediately after the write operation, we would always get a *0*. A **solution** to this could be moving the `WAIT` to the gateway; whenever it received the response of the `buy_ticket` function, it would perform a `WAIT` to check how many replicas have acknowledged the operation. If the value were not enough (as we have 1 replica per shard, not enough is just 0), the gateway would have to perform a rollback, executing `INCR tickets-counter` and `SREM purchased_tracking_ids client_id`.
^ac5a42

## benchmark:: WAIT inside `buy_ticket`
To perform this benchmark we must keep the same setup of this experiment except for the `buy_ticket` function.

### BUY operation with WAIT
```redis-cli
FUNCTION LOAD REPLACE "#!lua name=ticket_sales\nredis.register_function('buy_ticket', function(keys, args)\n  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then\n    return -1\n  else\n    local ticket_number = tonumber(redis.call('DECR', keys[2]))\n    if ticket_number < 0 then\n      return -2\n    else\n      redis.call('SADD', keys[1], args[1])\n   redis.call('WAIT', 1, 0)\n   return ticket_number\n    end\n  end\nend)"
```

In a human readable form:
```lua
if redis.call('SISMEMBER', keys[1], args[1]) == 1 then
   return -1
else
    local ticket_number = tonumber(redis.call('DECR', keys[2]))
	if ticket_number < 0 then
		return -2
    else
		redis.call('SADD', keys[1], args[1])
		redis.call('WAIT', 1, 0)
		return ticket_number
	end
end
```

### Results
![[unnumbered-tickets-master-replica-WAIT-BUY-function-V1.0-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-master-replica-WAIT-BUY-function-V1.0-benchmark.csv]]
```

The same benchmark has been performed with the replica stopped to see its behavior.
![[unnumbered-tickets-master-replicaPaused-WAIT-BUY-function-V1.0-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-master-replicaPaused-WAIT-BUY-function-V1.0-benchmark.csv]]
```
#todo Check why its faster with the replica paused.

---

The final proposition combining the solutions to the other problems is: **Sharding + Replication + Sentinel**.
- **Sharding** for the logical separation of the `ticket-counter`.
- **Replication** to quickly take over a failed node and ensure availability.
- **Sentinel** to monitor nodes and make a *replica* node to take over its *master* quickly when it fails. Whenever the original *master* node recovers, it will take the role of *replica* from there on out.

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
### benchmark:: AOF persistence with exhaustive *fsync*
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
> This is the same benchmark performed at [[Development/Redis#Benchmark Unnumbered tickets - unnumbered-tickets-request-lifecycle V0.1 - BUY operation]].

#### Results
![[unnumbered-tickets-master-replica-BUY-function-V0.1-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[unnumbered-tickets-master-replica-BUY-function-V0.1-benchmark.csv]]
```
In conclusion, the Redis server will be fast enough for the dimensions of the given task, but a solution must be given to be able to scale the system to a more demanding scenario.

# Gateways cluster
Same as [[Development/Experiments/Redis-Gateway_cluster-Load_balancer#Gateways cluster|Redis-Gateway_cluster-Load_balancer#Gateways cluster]].

# Load balancer
Same as [[Development/Experiments/Redis-Gateway_cluster-Load_balancer#Load balancer|Redis-Gateway_cluster-Load_balancer#Load balancer]].

# Next steps
- Test the **sharding** idea proposed in the [[#^4104cb]]. The experiment where this is tested is [[Development/Experiments/RedisSharding-GatewayCluster-LoadBalancer|RedisSharding-GatewayCluster-LoadBalancer]].
- #todo Test the translation of the `WAIT` operation to the gateways.