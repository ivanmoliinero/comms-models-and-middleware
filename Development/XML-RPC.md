---
type:
  - communication-protocol
---
> [!success] Pros
> - #pro
> 	- (Name:: **Interoperability**)
> 	- **Description**:: Clients do not need to use a concrete language or install libraries (as with Pyro needs Python and Pyro5)

> [!fail] Cons
> - #con
> 	- (Name:: **Stateless**)
> 	- **Description**:: It doesn't really matter in this scenario since there are not any restrictions per user (e.g. only 1 ticket per user).
> 		- #solution
> 		- [status:: pending]
> 			- **Description**:: It could be implemented with a database.
> - #con
> 	- (Name:: **HTTP stack**)
> 	- **Description**:: The overhead of using HTTP it's noticeable
> 		- #solution 
> 		- [status:: pending] #todo
> 			- **Description**:: Maybe some middle-ware is capable of diminish the overhead of the HTTP messages by maintaining the connection oppened.
^bff55e
