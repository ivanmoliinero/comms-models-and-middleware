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
3          1.52M    4       0       249112 (+7573)      21          
3          1.52M    4       0       257534 (+8422)      21          
3          1.52M    4       0       265884 (+8350)      21          
3          1.52M    4       0       275005 (+9121)      21          
3          1.52M    4       0       283997 (+8992)      21          
3          1.52M    4       0       292932 (+8935)      21          
3          1.52M    4       0       298651 (+5719)      21
"""

    calculate_redis_ops_average(raw_redis_data)