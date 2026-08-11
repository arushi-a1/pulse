variable "project_name" { type = string }
variable "environment" { type = string }
variable "max_receive_count" {
  type    = number
  default = 5
}
