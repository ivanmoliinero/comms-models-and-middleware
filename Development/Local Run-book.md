This run-book describes the process of launching the designed tickets selling system **locally**.

> [!danger]
> Remember to **remove the resource limits** configurations upon deploying this system non-locally.
# Redis
1. Creating the containers network
```shell
docker network create redis-test-net
```

2. Creating the container
```shell
docker run -d \
  --name redis-server-test \
  --network redis-test-net \
  --cpuset-cpus="0" \
  --memory="2g" \
  redis:latest
```

3. Load the function to Redis
```redis-cli
FUNCTION LOAD REPLACE "#!lua name=ticket_sales\nredis.register_function('buy_ticket', function(keys, args)\n  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then\n    return -1\n  else\n    local ticket_number = tonumber(redis.call('DECR', keys[2]))\n    if ticket_number < 0 then\n      return -2\n    else\n      redis.call('SADD', keys[1], args[1])\n      return ticket_number\n    end\n  end\nend)"
```

4. Set the initial state of the database
```redis-cli
DEL purchased_tracking_ids
SET tickets-counter 20000
```

> [!tip]
> These commands can be executed by running [[software-testing/redis-server/setup.sh]]
# Gateway
## [[software-testing/gateway/nginx.conf]]
> [!important] Fine-tunning
> Some values configured shall be set up in terms of the machine where the server runs on, such as:
> - `worker_processes`
> - `worker_connections`

1. Raise the OpenResty container
```bash
docker run -d \
  --name openresty-gateway \
  --network redis-test-net \
  --cpuset-cpus="1-4" \
  --memory="2g" \
  -p 8080:80 \
  -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro \
  openresty/openresty:latest
```

#check Try to connect to the API Gateway
```bash
# client 1: first purchase
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-001"

# client 1: retry
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-001"

# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-002"
```