"""Record each S3 drop in DynamoDB and alert on empty drops. Triggered via SNS."""

import json
import os
from datetime import UTC, datetime
from urllib.parse import unquote_plus

import boto3

dynamodb = boto3.client("dynamodb")
sns = boto3.client("sns")


def handler(event, context):
    recorded = 0
    for sns_record in event.get("Records", []):
        s3_event = json.loads(sns_record["Sns"]["Message"])
        for rec in s3_event.get("Records", []):
            # S3 event keys are URL-encoded (day=00 arrives as day%3D00)
            key = unquote_plus(rec["s3"]["object"]["key"])
            size = int(rec["s3"]["object"].get("size", 0))
            dynamodb.put_item(
                TableName=os.environ["MANIFEST_TABLE"],
                Item={
                    "object_key": {"S": key},
                    "bucket": {"S": rec["s3"]["bucket"]["name"]},
                    "size_bytes": {"N": str(size)},
                    "arrived_at": {"S": rec.get("eventTime", datetime.now(UTC).isoformat())},
                },
            )
            recorded += 1
            if size == 0:
                sns.publish(
                    TopicArn=os.environ["ALERT_TOPIC_ARN"],
                    Subject="Empty marketing drop",
                    Message=f"Drop {key} arrived with 0 bytes",
                )
    return {"recorded": recorded}
