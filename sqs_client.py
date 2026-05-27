import json
import boto3
import config

_client = None


def _sqs():
    global _client
    if _client is None:
        _client = boto3.client("sqs", region_name=config.AWS_REGION)
    return _client


def publish(queue_url: str, message: dict) -> None:
    _sqs().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),
    )

# long-poll for up to max_messages, eeturns raw SQS message dicts (Body + ReceiptHandle)
def consume(queue_url: str, max_messages: int = 10, wait_seconds: int = 20) -> list[dict]:
    response = _sqs().receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_seconds,
    )
    return response.get("Messages", [])


def delete(queue_url: str, receipt_handle: str) -> None:
    _sqs().delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )
