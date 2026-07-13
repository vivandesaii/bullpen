import boto3
import json
import asyncio
import uuid

from app.config import settings

sqs_client = boto3.client(
    'sqs',
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region
)

async def send_trade_message(trade_data: dict, user_id: int) -> dict:
    """Sends a trade message to the SQS queue and returns the response."""

    message_body = json.dumps(trade_data) # Serialize the trade data to a JSON string for sending to SQS
    dedup_id = str(uuid.uuid4())  # Generate a unique deduplication ID for the message
    
    def _send(): # Define a synchronous function to send the message to SQS
        return sqs_client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=message_body,
            MessageDeduplicationId=dedup_id,  # Required for FIFO queues
            MessageGroupId=str(user_id)  # Required for FIFO queues
        )
    
    return await asyncio.to_thread(_send)  # Run the SQS send operation in a separate thread to avoid blocking the event loop