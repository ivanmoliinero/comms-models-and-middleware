---
final-version: V0.0
environment: local
---


# Variants

Here some variants of this final version are purposed.
## Sentinels are the Redis masters and replicas themselves
#pro This could reduce the number of instances used, since we now have 3 instances dedicated to Sentinel functionalities.
#pro We could have a larger number of sentinels for a reduced cost, increasing the **fault tolerance**.
#con The number of sentinels may not be enough eventually if the system is too small (very few instances).
#con The number of sentinels might not be even, and given that it is a requirement, it could cause a problem.