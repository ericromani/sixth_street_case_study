import json
import csv
import boto3
import os
from io import StringIO

# Initialize S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Lambda handler triggered by S3 event notification.
    Reads a single-line CSV file from the source bucket,
    converts it to a JSON list, and writes it to the destination bucket.
    """
    try:
        # Extract bucket and object key from event
        record = event['Records'][0]
        source_bucket = record['s3']['bucket']['name']
        source_key = record['s3']['object']['key']

        # Destination bucket from environment variable
        destination_bucket = os.environ['DEST_BUCKET']
        destination_key = os.path.splitext(source_key)[0] + ".json"

        # Download the file from source bucket
        response = s3_client.get_object(Bucket=source_bucket, Key=source_key)
        file_content = response['Body'].read().decode('utf-8').strip()

        # Parse CSV (single line)
        csv_reader = csv.reader(StringIO(file_content))
        csv_row = next(csv_reader)  # Get the first (and only) row

        # Convert to JSON list
        json_data = json.dumps(csv_row)

        # Upload JSON to destination bucket
        s3_client.put_object(
            Bucket=destination_bucket,
            Key=destination_key,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )

        return {
            "statusCode": 200,
            "body": f"File {source_key} processed and saved as {destination_key} in {destination_bucket}"
        }

    except Exception as e:
        print(f"Error processing file: {e}")
        return {
            "statusCode": 500,
            "body": str(e)
        }
