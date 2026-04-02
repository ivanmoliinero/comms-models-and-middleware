> [!attention] Remember
> #testing
> **Workload scripts** already provided

## System
### Requirements
#requirement
- 20.000 tickets
- 2 ticket models:
- 2 communication architectures

> [!question]
> #wording-ambiguity
> Does this mean that I have to do 4 tasks instead of 1 really?
> > [!info] Answer

### Telemetry
#requirement
Gather and store information about **throughput, success/fail rate, number of workers**.

### Tickets
#### Unnumbered
The system must be able to sell **at most** 20.000 tickets.
> [!important] Remember
> In this version, **throughput and scalability** are the targets.
#### Numbered
Tickets from 1 to 20.000 are numbered and can be sold.
> [!important] Remember
> In this version, **consistency** under concurrency is the target.

## Task

### Direct communication
> [!important]
> #requirement
> Clients must send request to a **single entry point**.

> [!attention] Mandatory
> #requirement
> The **middleware** chosen must be one of the followings:
> - REST
> - XML-RPC
> - Pyro
### Indirect communication
> [!attention] Mandatory
> #requirement
> The only allowed **middleware** for this communication architecture is **RabbitMQ**.

## Testing
> [!error]
> #wording-error
> File `benchmark_unnumbered_20000.txt` contains exactly 20.000 request, thus, it is not capable of testing whether the system limits the number of sells to 20000 or not.

