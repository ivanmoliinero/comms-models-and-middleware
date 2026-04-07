-- Generates a highly randomized UUID string per request
request = function()
   local uuid = string.format("%04x%04x-%04x-%04x-%04x-%04x%04x%04x",
       math.random(0, 0xffff), math.random(0, 0xffff),
       math.random(0, 0xffff),
       math.random(0, 0x0fff) + 0x4000,
       math.random(0, 0x3fff) + 0x8000,
       math.random(0, 0xffff), math.random(0, 0xffff), math.random(0, 0xffff))
   return wrk.format("GET", "/buy?ticket_id=" .. uuid)
end
