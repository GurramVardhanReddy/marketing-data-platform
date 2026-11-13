resource "aws_s3_bucket" "raw" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# Drops are reloadable from the source file, so old versions move to cheaper storage then expire
resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "age-out-drops"
    status = "Enabled"
    filter { prefix = "raw/" }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

# Event-driven fan-out: every new drop goes to one SNS topic, which feeds Snowpipe and the manifest Lambda
resource "aws_sns_topic" "drops" {
  name = "${var.bucket_name}-drops"
}

data "aws_iam_policy_document" "sns_from_s3" {
  statement {
    sid       = "AllowBucketToPublish"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.drops.arn]
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.raw.arn]
    }
  }
  # Snowflake's account subscribes its own SQS queue to this topic for Snowpipe auto-ingest
  dynamic "statement" {
    for_each = var.snowflake_iam_user_arn == "" ? [] : [1]
    content {
      sid       = "AllowSnowflakeToSubscribe"
      actions   = ["SNS:Subscribe"]
      resources = [aws_sns_topic.drops.arn]
      principals {
        type        = "AWS"
        identifiers = [var.snowflake_iam_user_arn]
      }
    }
  }
}

resource "aws_sns_topic_policy" "drops" {
  arn    = aws_sns_topic.drops.arn
  policy = data.aws_iam_policy_document.sns_from_s3.json
}

resource "aws_s3_bucket_notification" "drops" {
  bucket = aws_s3_bucket.raw.id
  topic {
    topic_arn     = aws_sns_topic.drops.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "raw/impressions/"
    filter_suffix = ".parquet"
  }
  depends_on = [aws_sns_topic_policy.drops]
}
