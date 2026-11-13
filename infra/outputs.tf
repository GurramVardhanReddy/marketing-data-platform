output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "drops_topic_arn" {
  value = aws_sns_topic.drops.arn
}


output "manifest_table" {
  value = aws_dynamodb_table.drop_manifest.name
}

output "raw_bucket_arn" {
  value = aws_s3_bucket.raw.arn
}
