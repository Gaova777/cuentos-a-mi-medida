# The storage and the queue behind the story app, applied to LocalStack locally; pointed at a real account,
# only the provider block changes.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "endpoint" {
  description = "LocalStack's edge endpoint; empty for real AWS"
  type        = string
  default     = "http://localhost:4566"
}

variable "prefix" {
  type    = string
  default = "cuentos"
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3       = var.endpoint
    dynamodb = var.endpoint
    sqs      = var.endpoint
  }
}

# pages (images), narration (audio) and the story itself
resource "aws_s3_bucket" "books" {
  bucket        = "${var.prefix}-books"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "books" {
  bucket                  = aws_s3_bucket.books.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# stories never leave the machine, and they don't need to outlive the family's interest in them
resource "aws_s3_bucket_lifecycle_configuration" "books" {
  bucket = aws_s3_bucket.books.id
  rule {
    id     = "expire-after-a-year"
    status = "Enabled"
    filter {}
    expiration {
      days = 365
    }
  }
}

# the library: one item per story, with its status while it is being made
resource "aws_dynamodb_table" "library" {
  name         = "${var.prefix}-library"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "story_id"

  attribute {
    name = "story_id"
    type = "S"
  }
}

# story requests wait here for the one GPU worker
resource "aws_sqs_queue" "dead" {
  name = "${var.prefix}-jobs-dead"
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${var.prefix}-jobs"
  visibility_timeout_seconds = 600
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead.arn
    maxReceiveCount     = 3
  })
}

output "bucket" {
  value = aws_s3_bucket.books.bucket
}

output "table" {
  value = aws_dynamodb_table.library.name
}

output "queue_url" {
  value = aws_sqs_queue.jobs.url
}
