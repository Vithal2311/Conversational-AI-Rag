import boto3
from botocore.config import Config

s3 = boto3.client(
    "s3",
    region_name="ap-southeast-2",
    config=Config(
        connect_timeout=10,
        read_timeout=10,
        retries={"total_max_attempts": 1},
    ),
)

bucket = "company-doc-580064884025-ap-southeast-2-an"

print("Connecting to S3...", flush=True)

try:
    paginator = s3.get_paginator("list_objects_v2")
    count = 0
    print("Bucket:", bucket, flush=True)

    response = s3.list_objects_v2(Bucket=bucket)

    print("Objects returned:", response.get("KeyCount", 0))

    for item in response.get("Contents", []):
        print("Filename:", repr(item["Key"]))

    for page in paginator.paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            filename = item['Key']
            if not  filename.lower().endswith("txt"):
                continue
            response = s3.get_object(Bucket=bucket, Key=filename)
            body = response["Body"]
            try:
                text = body.read().decode("utf-8-sig")
            finally:
                body.close()
            count += 1
            print(f"\nFile: {filename}")
            print(f"Word count: {len(text.split())}")
            print(f"Preview: {text[:200]}")





    print(f"Connected successfully. Found {count} files.")

except Exception as error:
    print(f"Connection failed: {error}")