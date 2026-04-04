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
          1.52M    4       0       4299 (+2080)        89          
2          1.53M    4       0       6355 (+2056)        89          
2          1.52M    4       0       8414 (+2059)        89          
2          1.52M    4       0       10476 (+2062)       89          
2          1.52M    4       0       12544 (+2068)       89          
2          1.53M    4       0       14624 (+2080)       89          
2          1.53M    4       0       16695 (+2071)       89          
2          1.52M    4       0       18757 (+2062)       89          
2          1.52M    4       0       20816 (+2059)       89          
2          1.52M    4       0       22899 (+2083)       89          
2          1.53M    4       0       24982 (+2083)       89          
------- data ------ --------------------- load -------------------- - child -
keys       mem      clients blocked requests            connections          
2          1.53M    4       0       27050 (+2068)       89          
2          1.52M    4       0       29103 (+2053)       89          
2          1.52M    4       0       31171 (+2068)       89          
2          1.52M    4       0       33245 (+2074)       89          
2          1.53M    4       0       35304 (+2059)       89          
2          1.53M    4       0       37396 (+2092)       89          
2          1.52M    4       0       39323 (+1927)       89          
2          1.52M    4       0       41295 (+1972)       89          
2          1.52M    4       0       42247 (+952)        89          
2          1.53M    4       0       43856 (+1609)       89          
2          1.53M    4       0       45768 (+1912)       89          
2          1.52M    4       0       47689 (+1921)       89          
2          1.53M    4       0       49745 (+2056)       89          
2          1.53M    4       0       51825 (+2080)       89          
2          1.53M    4       0       53881 (+2056)       89          
2          1.52M    4       0       55949 (+2068)       89          
2          1.51M    4       0       58017 (+2068)       89          
2          1.53M    4       0       60079 (+2062)       89   
"""

    calculate_redis_ops_average(raw_redis_data)