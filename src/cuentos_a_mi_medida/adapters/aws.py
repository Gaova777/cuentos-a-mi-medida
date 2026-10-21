"""The library on AWS services (S3, DynamoDB, SQS), here LocalStack: the same code would run against a real account by
dropping AWS_ENDPOINT_URL. Names come from the Terraform outputs."""
import json
import os
import time
import uuid

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
PREFIX = os.environ.get("CUENTOS_PREFIX", "cuentos")


def _client(service: str):
    return boto3.client(service, endpoint_url=ENDPOINT or None, region_name="us-east-1",
                        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
                        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"))


class Library:
    def __init__(self):
        self.s3, self.db, self.sqs = _client("s3"), _client("dynamodb"), _client("sqs")
        self.bucket, self.table = f"{PREFIX}-books", f"{PREFIX}-library"
        self.queue = self.sqs.get_queue_url(QueueName=f"{PREFIX}-jobs")["QueueUrl"]

    # library items
    def create(self, request: dict) -> str:
        story_id = uuid.uuid4().hex[:12]
        self.db.put_item(TableName=self.table, Item={
            "story_id": {"S": story_id}, "status": {"S": "queued"}, "created": {"N": str(time.time())},
            "request": {"S": json.dumps(request, ensure_ascii=False)}})
        self.sqs.send_message(QueueUrl=self.queue, MessageBody=json.dumps({"story_id": story_id, **request}))
        return story_id

    def update(self, story_id: str, status: str, **fields):
        names = {"#s": "status", **{f"#{k}": k for k in fields}}
        values = {":s": {"S": status}, **{f":{k}": {"S": json.dumps(v, ensure_ascii=False)} for k, v in fields.items()}}
        expr = "SET #s = :s" + "".join(f", #{k} = :{k}" for k in fields)
        self.db.update_item(TableName=self.table, Key={"story_id": {"S": story_id}}, UpdateExpression=expr,
                            ExpressionAttributeNames=names, ExpressionAttributeValues=values)

    def get(self, story_id: str) -> dict | None:
        item = self.db.get_item(TableName=self.table, Key={"story_id": {"S": story_id}}).get("Item")
        return _plain(item) if item else None

    def all(self) -> list[dict]:
        items = [_plain(i) for i in self.db.scan(TableName=self.table).get("Items", [])]
        return sorted(items, key=lambda i: -i["created"])

    # files
    def put(self, key: str, body: bytes, content_type: str):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)

    def url(self, key: str, seconds: int = 3600) -> str:
        return self.s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key},
                                              ExpiresIn=seconds)

    def read(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    # queue
    def next_job(self, wait: int = 20) -> tuple[dict, str] | None:
        msgs = self.sqs.receive_message(QueueUrl=self.queue, MaxNumberOfMessages=1, WaitTimeSeconds=wait).get(
            "Messages", [])
        return (json.loads(msgs[0]["Body"]), msgs[0]["ReceiptHandle"]) if msgs else None

    def done(self, receipt: str):
        self.sqs.delete_message(QueueUrl=self.queue, ReceiptHandle=receipt)


def _plain(item: dict) -> dict:
    out = {}
    for k, v in item.items():
        if "N" in v:
            out[k] = float(v["N"])
        elif k in ("status", "story_id"):
            out[k] = v["S"]
        else:
            out[k] = json.loads(v["S"])
    return out
