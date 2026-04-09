---
final-version: V0.0
environment: AWS
tickets-mode: unnumbered
---
# Description

> [!important]
> This version is only prepared to handle **unnumbered tickets**.

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

#todo Indicate the machine chosen for each instance (i.e. t3.micro, t2.micro)

# Deploying

#todo Talk about the AWS CLI installation and IAM configuration.
#todo Document `terraform init` and `terraform apply`.
#todo Talk about the [[final-versions/unnumbered/V0.0/aws/main.tf]] file.

> [!info] Note
> - `control-plane-node-1` is the **load balancer**
> - `control-plane-node-2` and `control-plane-node-3` are **gateways**

```bash
$ aws ec2 describe-instances --query "Reservations[*].Instances[*].[Tags[?Key=='Name'].Value|[0], PublicIpAddress]" --output table
# output
--------------------------------------------
|             DescribeInstances            |
+-----------------------+------------------+
|  control-plane-node-2 |  13.218.159.191  |
|  redis-replica-a2     |  18.208.205.193  |
|  redis-replica-b1     |  3.235.15.47     |
|  redis-replica-a1     |  44.199.207.251  |
|  control-plane-node-3 |  44.193.3.109    |
|  redis-replica-b2     |  44.222.144.9    |
|  redis-master-a       |  32.195.68.240   |
|  redis-master-b       |  100.54.37.0     |
|  control-plane-node-1 |  44.215.107.90   |
+-----------------------+------------------+
```

```bash
$ aws ec2 describe-instances --query "Reservations[*].Instances[*].[Tags[?Key=='Name'].Value|[0], PrivateIpAddress]" --output table
----------------------------------------
|           DescribeInstances          |
+-----------------------+--------------+
|  control-plane-node-2 |  10.0.1.136  |
|  redis-replica-a2     |  10.0.1.231  |
|  redis-replica-b1     |  10.0.1.57   |
|  redis-replica-a1     |  10.0.1.138  |
|  control-plane-node-3 |  10.0.1.201  |
|  redis-replica-b2     |  10.0.1.146  |
|  redis-master-a       |  10.0.1.34   |
|  redis-master-b       |  10.0.1.92   |
|  control-plane-node-1 |  10.0.1.248  |
+-----------------------+--------------+

```

## Boot the Redis masters

> [!warning] Remember
> From here on out, customize the path to the targeted files such as the `.pem` one.

Perform the following for each master:
```bash
ssh -i SD-task1-key-pair.pem ubuntu@<master-public-ip>

# inside SSH -------------------------------------------------------------------
# Install Docker
sudo apt-get update && sudo apt-get install -y docker.io

# Boot the Master using AWS Host Networking
sudo docker run -d --name redis-master --network host redis:latest redis-server --appendonly yes --appendfsync always

# Disconnect from the EC2 instance
exit
```

## Boot the Redis replicas

Perform the following for each replica:

> [!warning]
> Remember to change the `--replicaof` `<ip>` parameter to be the private one of the respective shard's master (e.g. use *redis-master-a* private ip (which is 10.0.1.34) for *redis-replica-a1*).

```bash
ssh -i SD-task1-key-pair.pem ubuntu@<replica-public-ip>

# inside SSH -------------------------------------------------------------------
sudo apt-get update && sudo apt-get install -y docker.io
# Notice we use Master A's Private IP (10.0.1.34) for the replica connection
sudo docker run -d --name redis-replica --network host redis:latest redis-server --replicaof <if A-shard-replica=10.0.1.34 | if B-shard-replica=10.0.1.92> 6379 --appendonly yes --appendfsync always
exit
```

## check:: Security group config and replication

We will be performing intermediate checks to ensure that any step of the deployment fails. This way, if anything fails, we will have a simpler system to debug.

In this check we will check in one single command both **security group config** and **Redis replication** for the shard A.

```bash
ssh -i SD-task1-key-pair.pem ubuntu@10.0.1.34

# inside SSH -------------------------------------------------------------------
sudo docker exec -it redis-master redis-cli INFO replication
# output
# Replication
role:master
connected_slaves:2
slave0:ip=10.0.1.138,port=6379,state=online,offset=644,lag=0,io-thread=0
slave1:ip=10.0.1.231,port=6379,state=online,offset=644,lag=0,io-thread=0
# ... (skipped output)
```

We must focus on the `connected_slaves:2` value. Such confirms that the replication it's working, and the security group inbound rule is allowing internal traffic to port 6379.

## Load LUA functions and data into the Redis masters

Do this for each *redis-master*.
```bash
ssh -i SD-task1-key-pair.pem ubuntu@<redis-master-public-ip>

# inside SSH -------------------------------------------------------------------
cat << 'EOF' | sudo docker exec -i redis-master redis-cli -x FUNCTION LOAD REPLACE
#!lua name=ticket_sales
redis.register_function('buy_ticket', function(keys, args)
  if redis.call('SISMEMBER', keys[1], args[1]) == 1 then return -1 end
  local t = tonumber(redis.call('DECR', keys[2]))
  if t < 0 then return -2 else redis.call('SADD', keys[1], args[1]); return t end
end)
redis.register_function('rollback_ticket', function(keys, args)
  if redis.call('SREM', keys[1], args[1]) == 1 then return redis.call('INCR', keys[2]) end
  return 0
end)
EOF
sudo docker exec redis-master redis-cli SET tickets-counter 10000
exit
```

> [!note]
> We will be loading 10.000 tickets to each Redis shard.

## Set up the Sentinels (Load Balancer and Gateways)

For each `control-plane-node-x`:

```bash
sudo apt-get update && sudo apt-get install -y docker.io

sudo docker run -d --name redis-sentinel --network host redis:latest sh -c \
"echo 'port 26379' > /tmp/sentinel.conf && \
 echo 'sentinel monitor shard-a 10.0.1.34 6379 2' >> /tmp/sentinel.conf && \
 echo 'sentinel monitor shard-b 10.0.1.92 6379 2' >> /tmp/sentinel.conf && \
 echo 'sentinel down-after-milliseconds shard-a 3000' >> /tmp/sentinel.conf && \
 echo 'sentinel down-after-milliseconds shard-b 3000' >> /tmp/sentinel.conf && \
 redis-sentinel /tmp/sentinel.conf"
```

## Deploy the Gateways

For each gateway:
```bash
# upload the nginx.conf file
scp -i SD-task1-key-pair.pem nginx.conf ubuntu@<gateway-public-ip>:.
ssh -i SD-task1-key-pair.pem ubuntu@<gateway-public-ip>

# inside SSH -------------------------------------------------------------------
sudo docker run -d --name api-gateway --network host -v $(pwd)/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf:ro openresty/openresty:latest
```

> [!important]
> The previous command must be run from the path that contains the [[final-versions/V0.0/gateway/nginx.conf]] file.

## Deploy the Load Balancer

```bash
# upload the nginx-lb.conf
scp -i SD-task1-key-pair.pem nginx.conf ubuntu@<load-balancer-public-ip>:.
ssh -i SD-task1-key-pair.pem ubuntu@<load-balancer-public-ip>

# inside SSH -------------------------------------------------------------------
sudo docker run -d --name load-balancer --network host -v $(pwd)/nginx-lb.conf:/etc/nginx/nginx.conf:ro nginx:latest
```

> [!important]
> The previous command must be run from the path that contains the [[final-versions/V0.0/load-balancer/nginx-lb.conf]] file.

## check:: Client request

This is the litmus test, the following commands will put to the test the full lifecycle of the requests.
### First purchase

```bash
# client 1: first purchase
curl -i "http://44.193.24.57/buy?ticket_id=aws-production-001"
# output
{"ip":"10.0.1.34","shard":"shard-a","ticket":9999,"status":"success"}
```

```bash
# client 1: first purchase
curl -i "http://44.193.24.57/buy?ticket_id=aws-production-004"
# output
{"ip":"10.0.1.92","shard":"shard-b","ticket":9999,"status":"success"}
```
### Retry

```bash
# client 1: retry
curl -i "http://44.193.24.57/buy?ticket_id=aws-production-001"
# output
{"error":"Ticket already purchased"}
```

```bash
# client 1: first purchase
curl -i "http://44.193.24.57/buy?ticket_id=aws-production-004"
# output
{"error":"Ticket already purchased"}
```

## check:: First shard sells out

With this test we enter in the edge cases zone, starting with the main shard of a client running out of tickets.

1. Simulate running out of tickets for shard B
```bash
ssh -i SD-task1-key-pair.pem ubuntu@<redis-master-b-public-ip>

# inside SSH -------------------------------------------------------------------
sudo docker exec -it redis-master redis-cli
```

```redis-cli
FLUSHALL
SET tickets-counter 0
exit
```

> [!info] Note
> The `FLUSHALL` command in the `redis-cli` allows us to repeat a first purchase with the `ticket_id=aws-production-004`.

```bash
exit
# outside SSH ------------------------------------------------------------------
curl -i "http://44.193.24.57/buy?ticket_id=aws-production-004"
# output
{"shard":"shard-a","ip":"10.0.1.34","status":"success","ticket":9999}
```

As expected, the request has been redirected to the *shard A*.

## check:: Both shards sell out

1. Simulate running out of tickets in both shards.
For each *redis-master-x*:

```bash
ssh -i SD-task1-key-pair.pem ubuntu@<redis-master-x-public-ip>

# inside SSH -------------------------------------------------------------------
sudo docker exec -it redis-master redis-cli
```

```redis-cli
FLUSHALL
SET tickets-counter 0
exit
```

```bash
exit
# outside SSH ------------------------------------------------------------------
curl -i "http://44.193.24.57/buy?ticket_id=aws-production-004"
# output
{"error":"Tickets sold out completely"}
```

# Benchmarks

## benchmark:: Throughput

Locally, run the following from the path where [[final-versions/unnumbered/V0.0/benchmarks/k6_benchmark_unnumbered.js]] and [[benchmarks/benchmark_unnumbered_20000.txt]] reside.

```bash
sudo docker run --rm \
  --network host \
  -v $(pwd)/benchmark_unnumbered_20000.txt:/benchmark_data.txt:ro \
  -v $(pwd)/k6_benchmark_unnumbered.js:/k6_benchmark.js:ro \
  grafana/k6 run /k6_benchmark.js
  
# output
  █ TOTAL RESULTS 

    checks_total.......: 80000  3549.807772/s
    checks_succeeded...: 25.00% 20000 out of 80000
    checks_failed......: 75.00% 60000 out of 80000

    ✓ Success (200 OK)
    ✗ Duplicate ID (409 Conflict)
      ↳  0% — ✓ 0 / ✗ 20000
    ✗ Sold Out (410 Gone)
      ↳  0% — ✓ 0 / ✗ 20000
    ✗ Gateway/DB Error (500+)
      ↳  0% — ✓ 0 / ✗ 20000

    HTTP
    http_req_duration..............: avg=111.57ms min=96.06ms med=110.13ms max=550.63ms p(90)=115.29ms p(95)=117.38ms
      { expected_response:true }...: avg=111.57ms min=96.06ms med=110.13ms max=550.63ms p(90)=115.29ms p(95)=117.38ms
    http_req_failed................: 0.00%  0 out of 20000
    http_reqs......................: 20000  887.451943/s

    EXECUTION
    iteration_duration.............: avg=112.39ms min=96.18ms med=110.27ms max=550.72ms p(90)=115.41ms p(95)=117.53ms
    iterations.....................: 20000  887.451943/s
    vus............................: 100    min=100        max=100
    vus_max........................: 100    min=100        max=100

    NETWORK
    data_received..................: 4.9 MB 216 kB/s
    data_sent......................: 2.0 MB 87 kB/s




running (00m22.5s), 000/100 VUs, 20000 complete and 0 interrupted iterations
exact_requests ✓ [ 100% ] 100 VUs  00m22.5s/10m0s  20000/20000 shared iters
```

This could seem a very low RPS number, so let's see where the bottleneck sits performing a [[#benchmark Redis loopback|localhost benchmark]] to a *redis-master*.
## benchmark:: Redis loopback

> [!warning] Important
> The following benchmark has been ran from the same machine that it's being tested. This could harm the results of it, but since Redis is primarily *single-threaded* it won't affect the results.

```bash
ssh -i SD-task1-key-pair.pem ubuntu@<redis-master-a>

# inside SSH -------------------------------------------------------------------
sudo docker run --rm     --network host  redis:latest    redis-benchmark -h 127.0.0.1 -c 5 -n 20000 -q --threads 5 -r 1000000 --csv        fcall buy_ticket 2 purchased_tracking_ids tickets-counter __rand_int__
"test","rps","avg_latency_ms","min_latency_ms","p50_latency_ms","p95_latency_ms","p99_latency_ms","max_latency_ms"
"fcall buy_ticket 2 purchased_tracking_ids tickets-counter __rand_int__","961.72","5.155","2.416","5.799","6.135","6.399","12.783"
```

![[final-versions/unnumbered/V0.0/benchmarks/rdis-master-a-localhost-benchmark.csv]]
```csvtable
columns:
- test
- rps
- p99_latency_ms	
source: [[final-versions/unnumbered/V0.0/benchmarks/rdis-master-a-localhost-benchmark.csv]]
```
Those are awful RPS and latency values considering this test was run in the *loopback* network. This shows the real bottleneck of the system, thus, it could be proved by increasing the number of shards, or the speed of the storage media.

# Variants

## variant:: Migrating to a problem-specialized database

One of the conclusions of making this project, is that Redis is not the most suited database for this tasks. Note that we had been disabling all advantages of Redis against other databases throughout the development, such as working at the speeds of RAM and asynchronous replication. This caused the performance of Redis to reduce, maybe to the point where another more problem-specialized database would perform better.