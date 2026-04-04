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
          1.52M    4       0       15659 (+1816)       5           
2          1.52M    4       0       17538 (+1879)       5           
2          1.52M    4       0       19390 (+1852)       5           
2          1.53M    4       0       21278 (+1888)       5           
2          1.52M    4       0       23139 (+1861)       5           
2          1.52M    4       0       24877 (+1738)       5           
2          1.52M    4       0       26699 (+1822)       5           
2          1.52M    4       0       28539 (+1840)       5           
2          1.53M    4       0       30397 (+1858)       5           
2          1.53M    4       0       32249 (+1852)       5           
2          1.52M    4       0       34023 (+1774)       5           
2          1.53M    4       0       35881 (+1858)       5           
2          1.53M    4       0       37796 (+1915)       5           
2          1.52M    4       0       39657 (+1861)       5           
2          1.52M    4       0       41494 (+1837)       5           
2          1.53M    4       0       43382 (+1888)       5           
2          1.52M    4       0       45270 (+1888)       5           
2          1.52M    4       0       47197 (+1927)       5           
2          1.53M    4       0       49022 (+1825)       5           
------- data ------ --------------------- load -------------------- - child -
keys       mem      clients blocked requests            connections          
2          1.53M    4       0       50883 (+1861)       5           
2          1.51M    4       0       52561 (+1678)       5           
2          1.52M    4       0       54212 (+1651)       5           
2          1.52M    4       0       54822 (+610)        5           
2          1.53M    4       0       55681 (+859)        5           
2          1.53M    4       0       57314 (+1633)       5           
2          1.53M    4       0       59001 (+1687)       5           
3          1.52M    4       0       60060 (+1059)       5    
"""

    calculate_redis_ops_average(raw_redis_data)