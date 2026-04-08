---
final-version: V0.0
environment: local
---


# Variants

Here some variants of this final version are purposed.
## variant:: Masters and replicas are also sentinels

> [!success] Pros
> - This could reduce the number of instances used, since we now have 3 instances dedicated to Sentinel functionalities.
> - We could have a larger number of sentinels for a reduced cost, increasing the **fault tolerance**.

> [!fail] Cons
> - The number of sentinels may not be enough eventually if the system is too small (very few instances).
> - The number of sentinels might not be even, and given that it is a requirement, it could cause a problem.


## variant:: The gateways are also sentinels
> [!success] Pros
> - This could **reduce the number of instances** used, since we now have 3 instances dedicated to Sentinel functionalities.
> - We could have a larger number of sentinels for a reduced cost, increasing the **fault tolerance**.

> [!fail] Cons
> - The number of sentinels may not be enough eventually if the system is too small (very few instances).
> - The number of sentinels might not be even, and given that it is a requirement, it could cause a problem.

## variant:: A combination of [[#variant Masters and replicas are also sentinels]] and [[#variant The gateways are also sentinels]]

> [!success] Pros
> - Could reduce the counterpart mentioned in both variants about the eventual insufficient number of sentinels.

## variant:: Migrating to a problem-specialized database

One of the conclusions of making this project, is that Redis is not the most suited database for this tasks. Note that we had been disabling all advantages of Redis against other databases throughout the development, such as working at the speeds of RAM and asynchronous replication. This caused the performance of Redis to reduce, maybe to the point where another more problem-specialized database would perform better.