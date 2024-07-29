from functions import get_lambda_functions, get_lambda_metrics, calculate_sli_averages, csv

# Main function to gather metrics for all functions and write to CSV
def main():
    pattern = r".*ms-workflow-.*"  # Regex pattern to match function names
    lambda_functions = get_lambda_functions(pattern)
    
    if not lambda_functions:
        print("No Lambda functions found matching the pattern.")
        return

    all_metrics = []
    
    for function in lambda_functions:
        print(f"Fetching metrics for {function}...")
        metrics = get_lambda_metrics(function)
        for metric, data_points in metrics.items():
            for data_point in data_points:
                sample_count = data_point.get('SampleCount', 0)
                sum_value = data_point.get('Sum', 0)
                p99_value = data_point.get('ExtendedStatistics', {}).get('p99', 0)
                if p99_value != 0:
                    one_percent_count = sample_count * 0.01
                else:
                    one_percent_count = 'N/A'
                all_metrics.append({
                    'FunctionName': function,
                    'MetricName': metric,
                    'Timestamp': data_point['Timestamp'],
                    'Average': data_point.get('Average', 'N/A'),
                    'Sum': sum_value,
                    'p99': p99_value,
                    'SampleCount': sample_count,
                    'OnePercentCount': one_percent_count,
                })

    # Define CSV file name
    csv_file_name = 'lambda_metrics.csv'

    # Write metrics to CSV file
    with open(csv_file_name, mode='w', newline='') as csv_file:
        fieldnames = ['FunctionName', 'MetricName', 'Timestamp', 'Average', 'Sum', 'p99', 'SampleCount', 'OnePercentCount']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for metric in all_metrics:
            writer.writerow(metric)

    print(f"Metrics have been written to {csv_file_name}")

    # Calculate SLI averages
    calculate_sli_averages(csv_file_name, 'SLI_average.csv')

    # Process CSV for latency SLO creation
    # process_csv('SLI_average.csv')

if __name__ == "__main__":
   main()