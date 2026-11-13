variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "bucket_name" {
  description = "The raw bucket created by the AWS stack"
  type        = string
}

variable "drops_topic_arn" {
  description = "drops_topic_arn output of the AWS stack"
  type        = string
}

variable "transformer_user" {
  description = "Snowflake user that dbt and Prefect run as"
  type        = string
}

variable "create_pipe" {
  description = "Set true on the second apply, after the AWS stack has the Snowflake principal"
  type        = bool
  default     = false
}
