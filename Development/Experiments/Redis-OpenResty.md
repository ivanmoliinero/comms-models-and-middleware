---
experiment: Redis+OpenResty(gateway)
environment: local
---
> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.
# Other preparations
1. Creating the containers network
```shell
docker network create redis-test-net
```

# Redis
1. Creating the container
```shell
docker run -d \
  --name redis-server-test \
  --network redis-test-net \
  --cpuset-cpus="0" \
  --memory="2g" \
  redis:latest
```

2. Load the function to Redis

>[!note]
> You must execute the following commands (steps 2 and 3) on the Redis server.

```redis-cli
FUNCTION LOAD REPLACE "#!lua name=ticket_sales\nredis.register_function('buy_ticket', function(keys, args)\n  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then\n    return -1\n  else\n    local ticket_number = tonumber(redis.call('DECR', keys[2]))\n    if ticket_number < 0 then\n      return -2\n    else\n      redis.call('SADD', keys[1], args[1])\n      return ticket_number\n    end\n  end\nend)"
```

3. Set the initial state of the database
```redis-cli
DEL purchased_tracking_ids
SET tickets-counter 20000
```

> [!tip]
> These commands can be executed by running [[software-testing/redis-server/setup.sh]]
# Gateway
> [!important] Fine-tunning
> Some values configured in the [[software-testing/redis-openResty/gateway/nginx.conf]] file shall be set up in terms of the machine where the server runs on, such as:
> - `worker_processes`
> - `worker_connections`

1. Raise the OpenResty container
```bash
docker run -d \
  --name openresty-gateway \
  --network redis-test-net \
  --cpuset-cpus="1" \
  --memory="1g" \
  -p 8080:80 \
  -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro \
  openresty/openresty:latest
```

> [!important]
> The previous command must be run from the path that contains the [[software-testing/redis-openResty/gateway/nginx.conf]] file

An important detail must be commented about the `nginx.conf` file used for the gateway.

```embed-shell
PATH: "vault://software-testing/redis-openResty/gateway/nginx.conf"
LINES: "6-9"
```

Note the `resolver` config it's necessary since *nginx* bypasses the OS DNS, and as we are using Docker's DNS we must indicate it to make the gateway see the Redis server's domain name (container's name).
# Checks
## Try to connect to the API Gateway
```bash
# client 1: first purchase
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-001"

# client 1: retry
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-001"

# client 2: first purchase
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-002"
```

### Expected
```bash
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-001"
# output
HTTP/1.1 200 OK
Server: openresty/1.29.2.3
Date: Fri, 03 Apr 2026 18:53:13 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"ticket_number":19999,"status":"success"}
# ----------------------------
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-001"
# output
HTTP/1.1 409 Conflict
Server: openresty/1.29.2.3
Date: Fri, 03 Apr 2026 18:56:18 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"message":"Ticket already purchased with this ID","status":"error"}
# ----------------------------
curl -i "http://localhost:8080/buy?ticket_id=client-uuid-002"
# output
HTTP/1.1 200 OK
Server: openresty/1.29.2.3
Date: Fri, 03 Apr 2026 18:56:23 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"ticket_number":19998,"status":"success"}
```