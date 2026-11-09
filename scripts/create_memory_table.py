"""Create the configured DynamoDB conversation table and enable TTL."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from workflow_logging import logged_step, logger


@logged_step
def main():
    import boto3
    from botocore.exceptions import ClientError
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    name = os.getenv('DYNAMODB_TABLE_NAME', '').strip()
    if not name:
        raise ValueError('Set DYNAMODB_TABLE_NAME in .env')
    client = boto3.client('dynamodb', region_name=os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-2'))
    schema = [{'AttributeName': 'session_id', 'KeyType': 'HASH'},
              {'AttributeName': 'message_id', 'KeyType': 'RANGE'}]
    try:
        client.describe_table(TableName=name)
    except ClientError as error:
        if error.response['Error']['Code'] != 'ResourceNotFoundException':
            raise
        client.create_table(TableName=name, KeySchema=schema,
                            AttributeDefinitions=[{'AttributeName': key['AttributeName'], 'AttributeType': 'S'}
                                                  for key in schema], BillingMode='PAY_PER_REQUEST')
    client.get_waiter('table_exists').wait(TableName=name)
    description = client.describe_table(TableName=name)['Table']
    if description['KeySchema'] != schema or any(
        field['AttributeType'] != 'S' for field in description['AttributeDefinitions']
        if field['AttributeName'] in {'session_id', 'message_id'}
    ):
        raise ValueError('Existing table has an incompatible key schema')
    ttl = client.describe_time_to_live(TableName=name)['TimeToLiveDescription']
    status = ttl['TimeToLiveStatus']
    if status == 'DISABLED':
        client.update_time_to_live(TableName=name, TimeToLiveSpecification={
            'Enabled': True, 'AttributeName': 'expires_at'})
    elif status not in {'ENABLED', 'ENABLING'} or ttl.get('AttributeName') != 'expires_at':
        raise ValueError('Existing TTL configuration is incompatible')
    logger.info('conversation table ready')


if __name__ == '__main__':
    main()
