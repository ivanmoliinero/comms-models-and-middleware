local requests = {}
local counter = 0

for line in io.lines("/benchmark_data.txt") do
    if not string.match(line, "^#") and line:match("%S") then
        local client_id, seat_id = string.match(line, "BUY%s+(%S+)%s+(%d+)")
        if client_id and seat_id then
            table.insert(requests, "/buy?ticket_id=" .. client_id .. "&seat_id=" .. seat_id)
        end
    end
end

request = function()
   counter = counter + 1
   if counter > #requests then
       wrk.thread:stop()
       return wrk.format("GET", "/")
   end
   return wrk.format("GET", requests[counter])
end
