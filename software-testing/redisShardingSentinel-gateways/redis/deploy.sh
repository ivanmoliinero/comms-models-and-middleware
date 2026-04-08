#!/bin/bash

echo "1. Cleaning up previous laboratory..."
docker rm -f master-a replica-a master-b replica-b master-c replica-c sentinel-1 sentinel-2 sentinel-3 2>/dev/null
docker network rm redis-test-net 2>/dev/null
docker network create redis-test-net

echo "2. Booting 3 Independent Masters..."
docker run -d --name master-a --network redis-test-net redis:latest redis-server --appendonly yes --appendfsync always
docker run -d --name master-b --network redis-test-net redis:latest redis-server --appendonly yes --appendfsync always
docker run -d --name master-c --network redis-test-net redis:latest redis-server --appendonly yes --appendfsync always

echo "3. Booting 3 Replicas (One for each Master)..."
docker run -d --name replica-a --network redis-test-net redis:latest redis-server --replicaof master-a 6379 --appendonly yes --appendfsync always
docker run -d --name replica-b --network redis-test-net redis:latest redis-server --replicaof master-b 6379 --appendonly yes --appendfsync always
docker run -d --name replica-c --network redis-test-net redis:latest redis-server --replicaof master-c 6379 --appendonly yes --appendfsync always

echo "4. Booting 3 Sentinel Nodes (The Quorum)..."
# We dynamically generate the sentinel.conf file inside the container so Sentinel has permission to rewrite it during a failover.
for i in 1 2 3; do
  docker run -d --name sentinel-$i --network redis-test-net redis:latest sh -c \
  "echo 'port 26379' > /tmp/sentinel.conf && \
   echo 'sentinel resolve-hostnames yes' >> /tmp/sentinel.conf && \
   echo 'sentinel monitor shard-a master-a 6379 2' >> /tmp/sentinel.conf && \
   echo 'sentinel monitor shard-b master-b 6379 2' >> /tmp/sentinel.conf && \
   echo 'sentinel monitor shard-c master-c 6379 2' >> /tmp/sentinel.conf && \
   echo 'sentinel down-after-milliseconds shard-a 3000' >> /tmp/sentinel.conf && \
   echo 'sentinel down-after-milliseconds shard-b 3000' >> /tmp/sentinel.conf && \
   echo 'sentinel down-after-milliseconds shard-c 3000' >> /tmp/sentinel.conf && \
   redis-sentinel /tmp/sentinel.conf"
done

echo "Deployment Complete. 9 Nodes running."
