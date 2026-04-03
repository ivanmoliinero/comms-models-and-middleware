docker network create redis-test-net

docker run -d \
  --name redis-server \
  --network redis-test-net \
  --cpuset-cpus="0" \
  --memory="2g" \
  redis:latest
