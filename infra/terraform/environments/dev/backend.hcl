# Usage: terraform init -backend-config=environments/dev/backend.hcl
# Bucket/table must be created once, out-of-band, before first init (a
# classic bootstrapping problem for remote state -- not something Terraform
# can create for itself on the very first run).

bucket         = "pulse-terraform-state-dev"   # replace with your own globally-unique bucket
key            = "pulse/dev/terraform.tfstate"
region         = "us-west-2"
dynamodb_table = "pulse-terraform-locks-dev"
encrypt        = true
