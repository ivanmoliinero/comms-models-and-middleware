---
type:
  - library
  - middleware
language: python
---
> [!success] Pros
> - #pro
> 	- (Name:: **Stateful**)
> 	- **Description**:: At first glance, not needed for anything in this scenario.
> - #pro
> 	- (Name:: **High Speed and Low Latency**)
> 	- **Description**:: Both extremely suited for this job. 

> [!fail] Cons
> - #con
> 	- (Name:: **Language and library dependent**)
> 	- **Description**:: Clients need Python and Pyro5 to be installed in their web browsers, this is not realistic. The architecture must add an additional layer to overcome with this problem.
>
> 	- #solution
> 		- [status:: rejected]
> 		- **Description**:: But this maybe comes with little cost since a load balancer it's needed, and thus, another layer must be included already.
> 	- #resolution
> 		- **Description**:: It's not reusing any layer since the load balancer and the API Gateway aren't likely the same server at all.
