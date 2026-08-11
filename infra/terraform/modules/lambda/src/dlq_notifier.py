"""
Fires when the CloudWatch alarm on DLQ depth (see the cloudwatch module)
changes state. Publishes a human-readable summary to SNS so on-call finds
out about a stuck event pipeline instead of discovering it via a support
ticket days later. Deliberately does nothing more than that -- no retries,
no reprocessing logic here; a human decides what to do with the DLQ.
"""
import json
import os

import boto3

sns = boto3.client("sns")
TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def handler(event, context):
    detail = event.get("detail", {})
    alarm_name = detail.get("alarmName", "unknown-alarm")
    new_state = detail.get("state", {}).get("value", "UNKNOWN")
    reason = detail.get("state", {}).get("reason", "")

    message = (
        f"Pulse alarm '{alarm_name}' is now {new_state}.\n\n{reason}\n\n"
        "This usually means events are landing in the dead-letter queue after "
        "exhausting retries. Check /analytics/failures and the worker logs "
        "in CloudWatch Logs Insights for the failing event_id(s)."
    )

    sns.publish(TopicArn=TOPIC_ARN, Subject=f"[Pulse] {alarm_name}: {new_state}", Message=message)
    return {"statusCode": 200, "body": json.dumps({"notified": True})}
