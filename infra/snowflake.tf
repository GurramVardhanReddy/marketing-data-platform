data "aws_caller_identity" "me" {}

locals {
  db                    = "MARKETING"
  snowflake_s3_role     = "${var.bucket_name}-snowflake-access"
  snowflake_s3_role_arn = "arn:aws:iam::${data.aws_caller_identity.me.account_id}:role/${local.snowflake_s3_role}"
  raw_columns = {
    TIMESTAMP             = "NUMBER(38,0)"
    UID                   = "NUMBER(38,0)"
    CAMPAIGN              = "NUMBER(38,0)"
    CONVERSION            = "NUMBER(38,0)"
    CONVERSION_TIMESTAMP  = "NUMBER(38,0)"
    CONVERSION_ID         = "NUMBER(38,0)"
    ATTRIBUTION           = "NUMBER(38,0)"
    CLICK                 = "NUMBER(38,0)"
    CLICK_POS             = "NUMBER(38,0)"
    CLICK_NB              = "NUMBER(38,0)"
    COST                  = "FLOAT"
    CPO                   = "FLOAT"
    TIME_SINCE_LAST_CLICK = "NUMBER(38,0)"
  }
}

# --- Storage integration: Snowflake reads the bucket through an IAM role it assumes ---
resource "snowflake_storage_integration_aws" "s3" {
  name                      = "MARKETING_S3"
  storage_provider          = "S3"
  enabled                   = true
  storage_allowed_locations = ["s3://${var.bucket_name}/raw/"]
  storage_aws_role_arn      = local.snowflake_s3_role_arn
}

data "aws_iam_policy_document" "snowflake_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [snowflake_storage_integration_aws.s3.describe_output[0].iam_user_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [snowflake_storage_integration_aws.s3.describe_output[0].external_id]
    }
  }
}

resource "aws_iam_role" "snowflake_access" {
  name               = local.snowflake_s3_role
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust.json
}

data "aws_iam_policy_document" "snowflake_read" {
  statement {
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.raw.arn}/raw/*"]
  }
  statement {
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.raw.arn]
  }
}

resource "aws_iam_role_policy" "snowflake_read" {
  role   = aws_iam_role.snowflake_access.id
  policy = data.aws_iam_policy_document.snowflake_read.json
}

# --- Database objects ---
resource "snowflake_database" "marketing" {
  name = local.db
}

resource "snowflake_schema" "layer" {
  for_each = toset(["RAW", "STAGING", "INTERMEDIATE", "MARTS", "SNAPSHOTS", "MONITOR"])
  database = snowflake_database.marketing.name
  name     = each.key
}

resource "snowflake_warehouse" "transform" {
  name           = "TRANSFORM_WH"
  warehouse_size = "XSMALL"
  auto_suspend   = 60
  auto_resume    = "true"
}

resource "snowflake_stage_external_s3" "drops" {
  name                = "IMPRESSION_DROPS"
  database            = snowflake_database.marketing.name
  schema              = snowflake_schema.layer["RAW"].name
  url                 = "s3://${var.bucket_name}/raw/impressions/"
  storage_integration = snowflake_storage_integration_aws.s3.name
  file_format {
    parquet {}
  }
}

resource "snowflake_table" "impressions" {
  database = snowflake_database.marketing.name
  schema   = snowflake_schema.layer["RAW"].name
  name     = "IMPRESSIONS"

  dynamic "column" {
    for_each = merge(local.raw_columns, { for i in range(1, 10) : "CAT${i}" => "NUMBER(38,0)" })
    content {
      name = column.key
      type = column.value
    }
  }
  column {
    name = "DAY"
    type = "NUMBER(38,0)"
  }
  column {
    name = "_SOURCE_FILE"
    type = "VARCHAR"
  }
  column {
    name = "_FILE_ROW_NUMBER"
    type = "NUMBER(38,0)"
  }
  column {
    name = "_LOADED_AT"
    type = "TIMESTAMP_NTZ(9)"
  }
}

# Snowpipe: auto-ingests each drop as soon as S3 announces it on the SNS topic
resource "snowflake_pipe" "impressions" {
  database          = snowflake_database.marketing.name
  schema            = snowflake_schema.layer["RAW"].name
  name              = "IMPRESSIONS_PIPE"
  auto_ingest       = true
  aws_sns_topic_arn = aws_sns_topic.drops.arn
  copy_statement    = <<-SQL
    COPY INTO ${snowflake_database.marketing.name}.RAW.IMPRESSIONS
    FROM (
      SELECT
        ${join(",\n        ", [for c in keys(local.raw_columns) : "$1:${lower(c)}"])},
        ${join(", ", [for i in range(1, 10) : "$1:cat${i}"])},
        REGEXP_SUBSTR(METADATA$FILENAME, 'day=([0-9]+)', 1, 1, 'e')::NUMBER,
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER,
        CURRENT_TIMESTAMP()::TIMESTAMP_NTZ
      FROM @${snowflake_database.marketing.name}.RAW.${snowflake_stage_external_s3.drops.name}
    )
  SQL
  depends_on        = [aws_iam_role_policy.snowflake_read, aws_sns_topic_policy.drops]
}

# --- Access: a TRANSFORMER role for dbt and Prefect, with least privilege ---
resource "snowflake_account_role" "transformer" {
  name = "TRANSFORMER"
}

resource "snowflake_grant_account_role" "transformer_to_user" {
  role_name = snowflake_account_role.transformer.name
  user_name = var.transformer_user
}

resource "snowflake_grant_privileges_to_account_role" "warehouse" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.transform.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.marketing.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "raw_read" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["SELECT"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.marketing.name}\".\"${snowflake_schema.layer["RAW"].name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "build_schemas" {
  for_each          = toset(["STAGING", "INTERMEDIATE", "MARTS", "SNAPSHOTS", "MONITOR"])
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
  on_schema {
    schema_name = "\"${snowflake_database.marketing.name}\".\"${snowflake_schema.layer[each.key].name}\""
  }
}
