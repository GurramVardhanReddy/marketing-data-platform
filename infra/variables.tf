variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "bucket_name" {
  description = "Globally unique name for the raw landing bucket"
  type        = string
}

variable "alert_email" {
  description = "Optional address subscribed to drop alerts (confirm the subscription email)"
  type        = string
  default     = ""
}

variable "snowflake_iam_user_arn" {
  description = "Snowflake's AWS principal from the snowflake stack's output. Empty until that stack is applied."
  type        = string
  default     = ""
}
