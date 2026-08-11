# This file lives at infra/terraform/environments/dev/ but symlinks/copies
# the root module in a typical layout. For this repo we keep a single root
# module (providers.tf, variables.tf, outputs.tf, main.tf all at
# infra/terraform/) and treat environments/dev/backend.hcl as the
# environment-specific piece, since Pulse only ships one environment.
# A second environment (e.g. staging) would add environments/staging/backend.hcl
# and be applied via:
#   terraform init -backend-config=environments/staging/backend.hcl
#   terraform apply -var-file=environments/staging/terraform.tfvars
