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