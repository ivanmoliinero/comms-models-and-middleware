We'll build a tickets selling system. The tickets will be unnumbered, so we only have to worry about the number of tickets sold.

This is an academical exercise, so we won't enter in some professional concerns, but I want you to be strict with any errors. As academical, it must use free software.
## Architectural design
### Sell life-cycle
> [!question] How does a client buy a ticket?
1. Client sends a REST request `tickets.concert/path`
2. The domain-name it's resolved giving the **API gateway's cluster load balancer's** IP
3. The request gets to the **API gateway's cluster load balancer** and is redirected to one of the **API gateways**.
4. The respective **API gateway** converts the request to a **Pyro** call.
5. The call needs to know where to be executed, so a **Pyro name-server** will act also as load balancer, redirecting the call to one of the **Pyro servers** registered.
6. The call gets executed. The executed function will have the following logic:
	1. Send a `DECR tickets-count` call to the **Redis server**. 
	2. The following is sent to the client that initiated the request:
	- If the response is `>= 0`, a message with the ticket number (likely the number returned from Redis).
	- Else, a message indicating that no more tickets are available is sent.
### Properties
#### Dynamic scaling
Wake up more instances of whatever cluster (gateways, Pyro servers) gets overwhelmed
#### Monitoring
Recent telemetry stored, and available to be converted to graphics.
#### Fault tolerance
Through the load balancers and replication.
Specifically talking about Redis, we'll use a master-slave set up to overcome with a master possible failure. The slave would take the role of master. We should also talk about persistence to ensure a crash in the server keeps the tickets counter.
#### Caching
When necessary, if performance would be highly affected if caching it's not used.
### Metrics
- **Request per second peak**: The system must be able to support a 50.000 client requests per second peak.
### Testing environment
To avoid the high costs testing this in production (cloud provider like AWS), we will run this in lab conditions, with a few physical computers. To simulate the need of scaling, we will create container instances with limite resources (e.g. 1 core, few RAM).