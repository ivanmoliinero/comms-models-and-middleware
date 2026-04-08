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
3          1.53M    4       0       122164 (+2028)      10          
3          1.52M    4       0       125024 (+2860)      10          
3          1.53M    4       0       129726 (+4702)      10          
3          1.52M    4       0       134608 (+4882)      10          
3          1.53M    4       0       139478 (+4870)      10          
3          1.52M    4       0       144330 (+4852)      10          
3          1.52M    4       0       149194 (+4864)      10          
3          1.52M    4       0       153935 (+4741)      10          
3          1.52M    4       0       158850 (+4915)      10          
3          1.52M    4       0       163663 (+4813)      10          
3          1.53M    4       0       168512 (+4849)      10          
3          1.52M    4       0       173418 (+4906)      10          
3          1.53M    4       0       178195 (+4777)      10          
3          1.52M    4       0       180154 (+1959)      10   
"""

    calculate_redis_ops_average(raw_redis_data)