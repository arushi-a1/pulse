variable "project_name" { type = string }
variable "environment" { type = string }
variable "account_suffix" {
  description = "Short unique suffix (e.g. AWS account id) to keep the globally-unique bucket name collision-free"
  type        = string
}
