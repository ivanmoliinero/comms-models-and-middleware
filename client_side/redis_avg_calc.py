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
3          2.70M    10      0       166196 (+1311)      19          
3          2.68M    10      0       169256 (+3060)      19          
3          2.68M    10      0       175614 (+6358)      19          
3          2.68M    10      0       182199 (+6585)      19          
3          2.70M    10      0       188818 (+6619)      19          
3          2.68M    10      0       194517 (+5699)      19          
3          2.68M    10      0       200693 (+6176)      19          
3          2.69M    10      0       207169 (+6476)      19          
3          2.69M    10      0       213428 (+6259)      19          
3          2.68M    10      0       220054 (+6626)      19          
3          2.68M    10      0       224974 (+4920)      19    
"""

    calculate_redis_ops_average(raw_redis_data)