#!/bin/bash

echo "1. Cleaning up previous laboratory..."
docker rm -f master-a master-b master-c replica-a1 replica-a2 replica-b1 replica-b2 replica-c1 replica-c2 sentinel-1 sentinel-2 sentinel-3 openresty-gateway 2>/dev/null
docker network rm redis-test-net 2>/dev/null
docker network create redis-test-net

echo "2. Booting 3 Independent Masters..."
for shard in a b c; do
  docker run -d --name master-$shard --network redis-test-net redis:latest redis-server --appendonly yes --appendfsync always
done

echo "3. Booting 6 Replicas (Two for each Master)..."
for shard in a b c; do
  docker run -d --name replica-${shard}1 --network redis-test-net redis:latest redis-server --replicaof master-$shard 6379 --appendonly yes --appendfsync always
  docker run -d --name replica-${shard}2 --network redis-test-net redis:latest redis-server --replicaof master-$shard 6379 --appendonly yes --appendfsync always
done

echo "4. Booting 3 Sentinel Nodes (The Quorum)..."
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

echo "Deployment Complete. 12 Database Nodes running."
