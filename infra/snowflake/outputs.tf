output "iam_user_arn" {
  description = "Pass to the AWS stack as snowflake_iam_user_arn"
  value       = snowflake_storage_integration_aws.s3.describe_output[0].iam_user_arn
}

output "snowpipe" {
  value = var.create_pipe ? "${snowflake_database.marketing.name}.RAW.${snowflake_pipe.impressions[0].name}" : "not created yet (create_pipe = false)"
}
