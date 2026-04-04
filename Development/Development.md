## System
### Tickets
#### Numbered
> [!Tip] idea:: [[Redis]]
> A good idea to release some pressure to the master Redis server is to create a **read-only replica**. The way this could work is by making clients (Pyro servers that will perform the request) to ask first to the **read-only** replica if their ticket number has already been registered as sold. This would relieve the master that otherwise would take care of every single request.
> However, this is not actually necessary since the throughput of Redis is high enough to handle 
### Communication type
#### Direct

> [!question] Speed comparison: XML-RPC vs Pyro
> Which is faster? => Make a test
> > [!answer]
> > Pyro it's undoubtedly faster

#decision Due to the increase in the number of layers in the system when using Pyro, REST has been decided to be the direct communication method by offering the interoperability and being faster than XML-RPC.
##### Implementation
The architectural and abstract design of the system [[direct-communication-design]] must be implement by choosing the software that will do the expected task, this section defines the elections made.

Here are some possible stacks that were available to be chosen:
- **Option 1:**
	- *Load balancer*: HAProxy or [[Nginx]]
	- *Gateway*: [[FastAPI]]
- **Option 2*:
	- *Load balancer*: HAProxy or [[Nginx]]
	- *Gateway*: [[OpenResty]]

#decision [[FastAPI]] works on Python, so it requires a running environment, and also running over Python, that is not precisely known by being extremely fast. By the other hand, OpenResty is made on purpose to build scalable high performance web services (among others), so without doing any benchmarks, the **Option 2** is preferred.

## Experiments
> [!important] Hardware
> The **hardware** used for every experiment is the following:
> > - RAM: 2 GB
> > - CPU: 1 core - Intel(R) Core(TM) i7-10870H CPU @ 2.20GHz
> 
> Note that this resource limits are software enforced, and not the real machine hardware capabilities. This is done because the tests are performed with 2 components: server, client; if the server is capable of getting the hole machine power, then the clients will not perform at its maximum, and viceversa.

```dataview
TABLE experiment
WHERE experiment
```
## Benchmarks
> [!important] Hardware
> The **hardware** used for every experiment is the following:
> > - RAM: 2 GB
> > - CPU: 1 core - Intel(R) Core(TM) i7-10870H CPU @ 2.20GHz
> 
> Note that this resource limits are software enforced, and not the real machine hardware capabilities. This is done because the tests are performed with 2 components: server, client; if the server is capable of getting the hole machine power, then the clients will not perform at its maximum, and viceversa.
```dataview
TABLE benchmark
WHERE benchmark
```
### benchmark:: Gateway: REST -> Pyro
How many requests will this gateway support?
#todo

