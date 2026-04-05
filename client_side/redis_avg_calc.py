import re


def calculate_redis_ops_average(redis_stats_output: str) -> float:
    """
    Parses a Redis stat string, extracts the instantaneous operations per second
    (the numbers inside the parentheses), and calculates the arithmetic mean.
    """
    # Regular expression to find digits inside parentheses, optionally prefixed by '+'
    # For example, it matches "(+1855)" and extracts "1855"
    pattern = r'\(\+?(\d+)\)'

    # Find all matching string values in the provided text
    matches = re.findall(pattern, redis_stats_output)

    if not matches:
        print("No operation metrics found in the provided string.")
        return 0.0

    # Convert the extracted string values into integers
    ops_values = [int(val) for val in matches]

    # Calculate the arithmetic mean
    total_sum = sum(ops_values)
    count = len(ops_values)
    average = total_sum / count

    print(f"Extracted {count} values.")
    print(f"Total Sum: {total_sum}")
    print(f"Average Operations Per Second: {average:.2f}")

    return average


# Example usage with a multi-line string
if __name__ == '__main__':
    raw_redis_data = """
          1.80M    10      0       6074 (+1813)        16          
2          1.85M    10      0       8023 (+1949)        16          
2          1.86M    10      0       10002 (+1979)       16          
2          1.89M    10      0       11935 (+1933)       16          
2          1.91M    10      0       13875 (+1940)       16          
2          1.93M    10      0       15787 (+1912)       16          
2          1.94M    10      0       17711 (+1924)       16          
2          1.95M    10      0       19641 (+1930)       16          
2          1.97M    10      0       21593 (+1952)       16          
2          2.00M    10      0       23504 (+1911)       16          
2          2.05M    10      0       25456 (+1952)       16          
2          2.06M    10      0       27347 (+1891)       16          
2          2.07M    10      0       29300 (+1953)       16          
2          2.10M    10      0       31290 (+1990)       16          
2          2.12M    10      0       33220 (+1930)       16          
2          2.14M    10      0       35159 (+1939)       16          
------- data ------ --------------------- load -------------------- - child -
keys       mem      clients blocked requests            connections          
2          2.16M    10      0       37094 (+1935)       16          
2          2.18M    10      0       39037 (+1943)       16          
2          2.20M    10      0       40985 (+1948)       16          
2          2.23M    10      0       42969 (+1984)       16          
2          2.26M    10      0       44960 (+1991)       16          
2          2.28M    10      0       46923 (+1963)       16          
2          2.29M    10      0       48873 (+1950)       16          
2          2.31M    10      0       50857 (+1984)       16          
2          2.33M    10      0       52764 (+1907)       16          
2          2.35M    10      0       54760 (+1996)       16          
2          2.37M    10      0       56683 (+1923)       16          
2          2.41M    10      0       58659 (+1976)       16          
2          2.43M    10      0       60623 (+1964)       16          
2          2.45M    10      0       62598 (+1975)       16
"""

    calculate_redis_ops_average(raw_redis_data)