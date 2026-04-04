---
experiment: Redis+GatewayCluster+LoadBalancer
---

> [!warning]
> This experiment has been performed under lab conditions, so bear in mind that **resource limits** have been applied to every component if it.

# Other preparations
Same as [[Development/Experiments/Redis-OpenResty#Other preparations|Redis-OpenResty#Other preparations]].

# Redis
Same as [[Development/Experiments/Redis-OpenResty#Redis|Redis-OpenResty#Redis]].

# Gateways cluster
In this experiment, we will launch **2 API gateways** to start treating the gateway as a cluster. Here are the steps to do it.

> [!tip]
> **Further details** are given in the [[Development/Experiments/Redis-OpenResty#Gateway|Redis-OpenResty#Gateway]] section.

1. Raise the 1º gateway instance
```bash
docker run -d \
  --name openresty-gateway-1 \
  --network redis-test-net \
  -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro \
  openresty/openresty:latest
```

2. Raise the 2º gateway instance
```bash
docker run -d \
  --name openresty-gateway-2 \
  --network redis-test-net \
  -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro \
  openresty/openresty:latest
```

# Load balancer
In this experiment, an [[Development/Nginx|Nginx]] instance will be the **load balancer**. This must be set up with the [[software-testing/redis-gateway_cluster-load_balancer/load-balancer/nginx-lb.conf]] config file.

This configures the **cluster's API gateway servers** to be used in a **Round-Robin** fashion.

1. Launch the load balancer instance
```bash
docker run -d \
  --name entry-load-balancer \
  --network redis-test-net \
  -p 8000:80 \
  -v $(pwd)/nginx-lb.conf:/etc/nginx/nginx.conf:ro \
  nginx:latest
```

> [!important]
> The previous command must be run from the path that contains the [[software-testing/redis-gateway_cluster-load_balancer/load-balancer/nginx-lb.conf]] file

# Checks
## Try to execute a buy operation
```bash
# client 3: first purchase
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-003"

# client 4: first purchase 
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-004"
```

### Expected
```bash
# client 3: first purchase
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-003"
# output
HTTP/1.1 200 OK
Server: nginx/1.29.7
Date: Fri, 03 Apr 2026 22:44:08 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"ticket_number":19999,"status":"success"}
# -----------------------------------------
# client 3: retry
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-003"
# output
HTTP/1.1 409 Conflict
Server: nginx/1.29.7
Date: Fri, 03 Apr 2026 22:44:22 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"status":"error","message":"Ticket already purchased with this ID"}
# -----------------------------------------
# client 4: first purchase 
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-004"
# output
HTTP/1.1 200 OK
Server: nginx/1.29.7
Date: Fri, 03 Apr 2026 22:44:32 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"ticket_number":19998,"status":"success"}
# -----------------------------------------
# client 4: retry
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-004"
# output
HTTP/1.1 409 Conflict
Server: nginx/1.29.7
Date: Fri, 03 Apr 2026 22:44:33 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"status":"error","message":"Ticket already purchased with this ID"}
# -----------------------------------------
```

In this point we force the system to have no more tickets available, so run the following within the Redis server:
```redis-cli
SET tickets-counter 0
```

Then check how the system behaves:

```bash
# client 3: retry
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-003"
# output
HTTP/1.1 409 Conflict
Server: nginx/1.29.7
Date: Fri, 03 Apr 2026 22:49:08 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"message":"Ticket already purchased with this ID","status":"error"}
# -----------------------------------------
# client 5: first purchase
curl -i "http://localhost:8000/buy?ticket_id=client-uuid-005"
# output
HTTP/1.1 410 Gone
Server: nginx/1.29.7
Date: Fri, 03 Apr 2026 22:49:50 GMT
Content-Type: application/json
Transfer-Encoding: chunked
Connection: keep-alive

{"status":"error","message":"Tickets sold out"}
# -----------------------------------------
```

This experiment can not be fully verified if we don't check which gateway is serving the clients' requests since we now have a load balancer (Round-Robin). So in order to do that we can check the **access logs** of the gateway servers.

```bash
docker logs openresty-gateway-1
# output
172.19.0.5 - - [03/Apr/2026:22:44:08 +0000] "GET /buy?ticket_id=client-uuid-003 HTTP/1.1" 200 54 "-" "curl/8.14.1"
172.19.0.5 - - [03/Apr/2026:22:44:32 +0000] "GET /buy?ticket_id=client-uuid-004 HTTP/1.1" 200 54 "-" "curl/8.14.1"
172.19.0.5 - - [03/Apr/2026:22:49:08 +0000] "GET /buy?ticket_id=client-uuid-003 HTTP/1.1" 409 80 "-" "curl/8.14.1"
# -----------------------------------------
docker logs openresty-gateway-2
# output
172.19.0.5 - - [03/Apr/2026:22:44:22 +0000] "GET /buy?ticket_id=client-uuid-003 HTTP/1.1" 409 80 "-" "curl/8.14.1"
172.19.0.5 - - [03/Apr/2026:22:44:33 +0000] "GET /buy?ticket_id=client-uuid-004 HTTP/1.1" 409 80 "-" "curl/8.14.1"
172.19.0.5 - - [03/Apr/2026:22:49:50 +0000] "GET /buy?ticket_id=client-uuid-005 HTTP/1.1" 410 59 "-" "curl/8.14.1"

```