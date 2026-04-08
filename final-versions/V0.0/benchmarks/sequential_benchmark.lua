-- sequential_benchmark.lua
local counter = 0

request = function()
   counter = counter + 1
   
   -- Format the integers to match your exact 5-digit specification
   local user_str = string.format("user%05d", counter)
   local ticket_str = string.format("%05d", counter)
   
   -- Concatenate to fit our current API schema
   local payload = user_str .. "_" .. ticket_str
   
   return wrk.format("GET", "/buy?ticket_id=" .. payload)
end
