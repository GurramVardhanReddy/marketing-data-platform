terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.3"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { project = "marketing-data-platform", managed_by = "terraform" }
  }
}

# Credentials come from the environment (SNOWFLAKE_ORGANIZATION_NAME, SNOWFLAKE_ACCOUNT_NAME,
# SNOWFLAKE_USER, SNOWFLAKE_AUTHENTICATOR=SNOWFLAKE_JWT, SNOWFLAKE_PRIVATE_KEY), never from files in the repo.
provider "snowflake" {
  role = "ACCOUNTADMIN"
  preview_features_enabled = [
    "snowflake_storage_integration_aws_resource",
    "snowflake_stage_external_s3_resource",
    "snowflake_pipe_resource",
    "snowflake_table_resource",
  ]
}
