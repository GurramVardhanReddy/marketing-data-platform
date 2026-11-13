# Manifest Lambda: records every drop (key, size, arrival time) in DynamoDB for lineage and audit,
# and publishes an alert when a drop is empty.
resource "aws_dynamodb_table" "drop_manifest" {
  name         = "${var.bucket_name}-drop-manifest"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "object_key"
  attribute {
    name = "object_key"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
}

resource "aws_sns_topic" "alerts" {
  name = "${var.bucket_name}-alerts"
}

resource "aws_sns_topic_subscription" "alert_email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

data "archive_file" "manifest" {
  type        = "zip"
  source_file = "${path.module}/lambda/manifest.py"
  output_path = "${path.module}/build/manifest.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "manifest" {
  name               = "${var.bucket_name}-manifest-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "manifest" {
  statement {
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.drop_manifest.arn]
  }
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

resource "aws_iam_role_policy" "manifest" {
  role   = aws_iam_role.manifest.id
  policy = data.aws_iam_policy_document.manifest.json
}

resource "aws_lambda_function" "manifest" {
  function_name    = "${var.bucket_name}-manifest"
  role             = aws_iam_role.manifest.arn
  runtime          = "python3.12"
  handler          = "manifest.handler"
  filename         = data.archive_file.manifest.output_path
  source_code_hash = data.archive_file.manifest.output_base64sha256
  timeout          = 30
  environment {
    variables = {
      MANIFEST_TABLE  = aws_dynamodb_table.drop_manifest.name
      ALERT_TOPIC_ARN = aws_sns_topic.alerts.arn
    }
  }
}

resource "aws_lambda_permission" "from_sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.manifest.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.drops.arn
}

resource "aws_sns_topic_subscription" "manifest" {
  topic_arn = aws_sns_topic.drops.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.manifest.arn
}
