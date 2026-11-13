output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "drops_topic_arn" {
  value = aws_sns_topic.drops.arn
}

output "snowpipe" {
  value = "${snowflake_database.marketing.name}.RAW.${snowflake_pipe.impressions.name}"
}
