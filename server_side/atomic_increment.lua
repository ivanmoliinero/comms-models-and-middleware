-- Script to increment atomically the redis counter for tickets.
local current_value = tonumber(redis.call('GET', KEYS[1]) or '0')
local max_value = tonumber(ARGV[1])

if current_value < max_value then
    return redis.call('INCR', KEYS[1])
else
    return -1
end