import boto3
import csv
import datetime
import re

# Initialize boto3 clients
cloudwatch = boto3.client('cloudwatch', region_name='ap-southeast-1')
lambda_client = boto3.client('lambda', region_name='ap-southeast-1')
application_signals_client = boto3.client('application-signals', region_name='ap-southeast-1')

# Function to list all Lambda functions that match the pattern
def get_lambda_functions(pattern):
    functions = []
    paginator = lambda_client.get_paginator('list_functions')
    for page in paginator.paginate():
        for function in page['Functions']:
            if re.match(pattern, function['FunctionName']):
                functions.append(function['FunctionName'])
    return functions

# Function to get metrics for a specific Lambda function
def get_lambda_metrics(function_name):
    metrics = [
        'Duration',
        'Errors',
        'Invocations',
        'Throttles'
    ]
    results = {}

    for metric in metrics:
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName=metric,
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                }
            ],
            StartTime=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60),
            EndTime=datetime.datetime.now(datetime.timezone.utc),
            Period=3600,  # 1 hour
            Statistics=['Average', 'Sum', 'SampleCount'],
            ExtendedStatistics=['p99']
        )

        # Extracting datapoints
        data_points = response['Datapoints']
        results[metric] = data_points

    return results

# Function to calculate SLI averages
def calculate_sli_averages(input_file, output_file):
    function_data = {}

    # Read the metrics data from CSV
    with open(input_file, mode='r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            function_name = row['FunctionName']
            if function_name not in function_data:
                function_data[function_name] = {
                    'Duration_p99_sum': 0,
                    'Duration_p99_count': 0,
                    'Errors_sum': 0,
                    'Invocations_sum': 0,
                    'Throttles_sum': 0
                }
            
            if row['MetricName'] == 'Duration' and row['p99'] != 'N/A':
                function_data[function_name]['Duration_p99_sum'] += float(row['p99'])
                function_data[function_name]['Duration_p99_count'] += 1
            
            if row['MetricName'] == 'Errors':
                function_data[function_name]['Errors_sum'] += float(row['Sum']) if row['Sum'] != 'N/A' else 0
            
            if row['MetricName'] == 'Invocations':
                function_data[function_name]['Invocations_sum'] += float(row['SampleCount']) if row['SampleCount'] != 'N/A' else 0
            
            if row['MetricName'] == 'Throttles':
                function_data[function_name]['Throttles_sum'] += float(row['Sum']) if row['Sum'] != 'N/A' else 0

    # Calculate SLI averages
    sli_averages = []
    for function_name, data in function_data.items():
        avg_p99_latency = data['Duration_p99_sum'] / data['Duration_p99_count'] if data['Duration_p99_count'] > 0 else 0
        total_invocations = data['Invocations_sum']
        total_errors = data['Errors_sum']
        total_throttles = data['Throttles_sum']
        
        availability = (1 - (total_errors / total_invocations)) * 100 if total_invocations > 0 else 0
        throughput = (1 - (total_throttles / total_invocations)) * 100 if total_invocations > 0 else 0

        sli_averages.append({
            'FunctionName': function_name,
            'AvgP99Latency': avg_p99_latency,
            'Availability': availability,
            'Throughput': throughput
        })

    # Print the results
    for i in sli_averages:
        print(i)

    # Write SLI averages to CSV
    with open(output_file, mode='w', newline='') as csv_file:
        fieldnames = ['FunctionName', 'AvgP99Latency', 'Availability', 'Throughput']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for sli in sli_averages:
            writer.writerow(sli)

    print(f"SLI averages have been written to {output_file}")

# Function to create latency SLO
def create_latency_slo(function_name, avg_p99_latency):
    slo_name = f"latency-{function_name}-slo"
    slo_description = f"Latency SLO for {function_name}"
    slo_latency_threshold = avg_p99_latency
    attainment_goal = 99.9  # 99% attainment goal
    warning_threshold = 30  # 30% warning threshold
    period_seconds = 60  # 1 minute period
    start_time = int(datetime.datetime.now().timestamp())  # Current time for StartTime

    # Create the SLO for latency
    try:
        response = application_signals_client.create_service_level_objective(
            Name=slo_name,
            Description=slo_description,
            SliConfig={
                'SliMetricConfig': {
                    'MetricDataQueries': [
                        {
                            'Id': 'm1',
                            'MetricStat': {
                                'Metric': {
                                    'Namespace': 'AWS/Lambda',
                                    'MetricName': 'Duration',
                                    'Dimensions': [
                                        {
                                            'Name': 'FunctionName',
                                            'Value': function_name
                                        }
                                    ]
                                },
                                'Period': period_seconds,
                                'Stat': 'Average',
                                'Unit': 'Milliseconds'
                            },
                            'ReturnData': True
                        }
                    ]
                },
                'MetricThreshold': slo_latency_threshold,
                'ComparisonOperator': 'LessThan'
            },
            Goal={
                'Interval': {
                    'CalendarInterval': {
                        'StartTime': start_time,
                        'DurationUnit': 'MONTH',
                        'Duration': 1
                    }
                },
                'AttainmentGoal': attainment_goal,
                'WarningThreshold': warning_threshold
            }
        )
        print(f"Latency SLO created for {function_name}: {response['Slo']['Arn']}")
    except Exception as e:
        print(f"Error creating Latency SLO for {function_name}: {e}")

# Function to process CSV for latency SLO creation
def process_csv(input_file):
    pattern = re.compile(r".*ms-workflow-.*")
    with open(input_file, mode='r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            function_name = row['FunctionName']
            if pattern.match(function_name):
                avg_p99_latency = int(float(row['AvgP99Latency'])) 
                create_latency_slo(function_name, avg_p99_latency)