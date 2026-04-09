local requests = {}
local counter = 0

-- io.lines lee el archivo secuencialmente. 
-- El archivo estará montado dentro del contenedor en la ruta /benchmark_data.txt
for line in io.lines("/benchmark_data.txt") do
    -- Ignorar comentarios (líneas que empiezan con #) y líneas vacías
    if not string.match(line, "^#") and line:match("%S") then
        -- string.match extrae el client_id y el seat_id basándose en el formato proporcionado
        local client_id, seat_id = string.match(line, "BUY%s+(%S+)%s+(%d+)")
        if client_id and seat_id then
            table.insert(requests, "/buy?ticket_id=" .. client_id .. "&seat_id=" .. seat_id)
        end
    end
end

request = function()
   counter = counter + 1
   if counter > #requests then
       -- wrk.thread:stop() es una función de la API interna de wrk que finaliza 
       -- explícitamente el hilo de ejecución. Esto evita que wrk vuelva a iterar 
       -- infinitamente sobre el array si el tiempo (-d) aún no se ha agotado.
       wrk.thread:stop()
       return wrk.format("GET", "/")
   end
   return wrk.format("GET", requests[counter])
end
