module "opensearch" {
  source                    = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/infrastructure/opensearch?ref=v2.0.0-opensearch"
  name                      = local.name
  cognito_admin_user_emails = concat(data.terraform_remote_state.account.outputs.admin_users, var.OPENSEARCH_ADMIN_EMAILS)
  cognito_user_emails = concat(data.terraform_remote_state.account.outputs.admin_users, var.OPENSEARCH_ADMIN_EMAILS)
  master_user_arn           = ""
  vpc_id                    = data.terraform_remote_state.vpc.outputs.vpc_id
  opensearch_instance_count = var.env == "prod" ? 3 : 1
  opensearch_instance_type  = var.env == "prod" ? "c5.xlarge.search" : "c5.large.search"
}
