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
    2          1.53M    4       0       3587 (+1855)        5           
2          1.53M    4       0       5358 (+1771)        5           
2          1.51M    4       0       7249 (+1891)        5           
2          1.52M    4       0       9092 (+1843)        5           
2          1.53M    4       0       10959 (+1867)       5           
2          1.53M    4       0       12856 (+1897)       5           
2          1.53M    4       0       14735 (+1879)       5           
2          1.52M    4       0       16605 (+1870)       5           
2          1.52M    4       0       18505 (+1900)       5           
2          1.52M    4       0       20357 (+1852)       5           
2          1.52M    4       0       22254 (+1897)       5           
------- data ------ --------------------- load -------------------- - child -
keys       mem      clients blocked requests            connections          
2          1.52M    4       0       24097 (+1843)       5           
2          1.53M    4       0       25979 (+1882)       5           
2          1.52M    4       0       27858 (+1879)       5           
2          1.52M    4       0       29746 (+1888)       5           
2          1.53M    4       0       31661 (+1915)       5           
2          1.53M    4       0       33291 (+1630)       5           
2          1.52M    4       0       34201 (+910)        5           
2          1.52M    4       0       35324 (+1123)       5           
2          1.53M    4       0       36903 (+1579)       5           
2          1.53M    4       0       38554 (+1651)       5           
2          1.53M    4       0       40343 (+1789)       5           
2          1.52M    4       0       42228 (+1885)       5           
2          1.52M    4       0       44080 (+1852)       5           
2          1.52M    4       0       45971 (+1891)       5           
2          1.53M    4       0       47844 (+1873)       5           
2          1.53M    4       0       49696 (+1852)       5           
2          1.52M    4       0       51542 (+1846)       5           
2          1.52M    4       0       53418 (+1876)       5           
2          1.52M    4       0       55270 (+1852)       5           
2          1.53M    4       0       57125 (+1855)       5           
------- data ------ --------------------- load -------------------- - child -
keys       mem      clients blocked requests            connections          
2          1.53M    4       0       58953 (+1828)        
    """

    calculate_redis_ops_average(raw_redis_data)