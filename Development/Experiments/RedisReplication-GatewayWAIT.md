---
experiment: RedisReplication-GatewayWAIT
environment: local
---
# Brief
In this experiment we will be testing the idea of moving the `WAIT` operation of the Redis master to the gateways.

> [!tip]
> This design pattern it's called Saga.

> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty|Redis-OpenResty]].

# Redis
1. Set up Redis just as we did in [[Development/Experiments/Redis_replication-Gateway_cluster-Load_balancer|Redis_replication-Gateway_cluster-Load_balancer]].

2. Add the functions `buy_ticket` and `rollbac_ticket` to the `redis-master`.
```
FUNCTION LOAD REPLACE "#!lua name=ticket_sales\nredis.register_function('buy_ticket', function(keys, args)\n  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then\n    return -1\n  else\n    local ticket_number = tonumber(redis.call('DECR', keys[2]))\n    if ticket_number < 0 then\n      return -2\n    else\n      redis.call('SADD', keys[1], args[1])\n      return ticket_number\n    end\n  end\nend)\n\nredis.register_function('rollback_ticket', function(keys, args)\n  if redis.call('SREM', keys[1], args[1]) == 1 then\n    return redis.call('INCR', keys[2])\n  end\n  return 0\nend)"
```

In a human readable form:

[function:: rollback_ticket]
```lua
if redis.call('SREM', keys[1], args[1]) == 1 then
    return redis.call('INCR', keys[2])
end
return 0
```

> [!info] Explanation
> You might be asking why did we add a `rollback_ticket` function. The reason is that we cannot make the *master* to rollback the `DECR` operation itself within the `buy_ticket` function when the number of acknowledgements it's not enough since we can't get the value of the `WAIT` inside it, as we've seen in the [[Development/Experiments/Redis_replication-Gateway_cluster-Load_balancer#^ac5a42|solution to lack of consistency]]. So we need to provide the gateway with something to do this rollback. What the function does is to check whether the client bought the ticket successfully or not, and based on that, we know if we have to increment the `tickets-counter` or not.

# Gateway

1. Spin up the **gateway**.

```bash
docker run -d --rm --name openresty-gateway --network redis-test-net \
	-p 8080:80 -v \
	$(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro openresty/openresty:latest
```

> [!important]
> The previous command must be run from the path that contains the [[software-testing/redisReplication-gatewayWAIT/gateway/nginx.conf]] file.

> [!important]
> One think must be said about the new `nginx.conf` file. A problem was encountered during the development of this experiment. The **socket read timeout** (configured with `red: set_timeouts`) was the same amount of the `red:wait` operation. This caused the socket to be closed before the rollback operation could be sent. In consequence, the rollback was never being sent.
> To fix this, the **read timeout** has been increased to 2000 ms. This can be seen at the following line of the file:
> ```embed-bash
> PATH: "vault://software-testing/redisShardingSentinel-gateways/gateway/nginx.conf"
> LINES: "73"
> ```

# Benchmarks
## Full HTTP lifecycle

This benchmark will test the **full HTTP lifecycle** of the system, simulating clients directly (contrary to what we were used to by using the `redis-benchmark` tool that skipped the gateway). To do so, we will be using a LUA script:

```embed-bash
PATH: "vault://software-testing/redisReplication-gatewayWAIT/benchmarks/benchmark.lua"
```

1. Spin up the container that will perform the benchmark.
```bash
sudo docker run --rm --network redis-test-net -v $(pwd)/benchmark.lua:/benchmark.lua williamyeh/wrk -t5 -c100 -d10s -s /benchmark.lua http://openresty-gateway/buy
```

- `-t`: OS threads
- `-c`: 100 clients (TCP connections)
- `-d`: 10s duration

> [!important]
> The previous command must be run from the path that contains the [[software-testing/redisReplication-gatewayWAIT/benchmarks/benchmark.lua|benchmark.lua]] file.

> [!info]
> Note that we are using the `williamyeh/wrk` container to use the tool `wrk`.

### Results
![[unnumbered-tickets-master-replica-BUY-function-V0.1-gatewayWAIT-benchmark.txt]]
```embed-bash
PATH: "vault://unnumbered-tickets-master-replica-BUY-function-V0.1-gatewayWAIT-benchmark.txt"
```

> [!warning]
> These results show an incredible throughput, though, we must take into account that this has been fully executed in **localhost**.

