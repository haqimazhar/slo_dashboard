import boto3
import csv
import re
from datetime import datetime

# Initialize boto3 client
client = boto3.client('application-signals', region_name='ap-southeast-1')

def create_latency_slo(function_name, avg_p99_latency):
    slo_name = f"latency-{function_name}-slo"
    slo_description = f"Latency SLO for {function_name}"
    slo_latency_threshold = avg_p99_latency
    attainment_goal = 99.9  # 99% attainment goal
    warning_threshold = 30  # 30% warning threshold
    period_seconds = 60  # 1 minute period
    start_time = 1721964752  # Current time for StartTime

    # Create the SLO for latency
    try:
        response = client.create_service_level_objective(
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

def process_csv(input_file):
    pattern = re.compile(r".*ms-workflow-.*")
    with open(input_file, mode='r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            function_name = row['FunctionName']
            if pattern.match(function_name):
                avg_p99_latency = int(float(row['AvgP99Latency'])) 
                create_latency_slo(function_name, avg_p99_latency)

if __name__ == "__main__":
    process_csv('SLI_average.csv')