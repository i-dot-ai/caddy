locals {
  # Add secrets to this list as required to make them available within the container.
  # Values must not be hardcoded here - they must either be references or updated in SSM Parameter Store.
  env_secrets = [
    {
      name  = "DATA_S3_BUCKET"
      value = module.app_bucket.id
    },
    {
      name  = "BACKEND_TOKEN"
      value = var.BACKEND_TOKEN
    },
    {
      name  = "POSTGRES_HOST"
      value = module.rds.db_instance_address
    },
    {
      name  = "POSTGRES_PORT"
      value = 5432
    },
    {
      name  = "POSTGRES_DB"
      value = module.rds.db_instance_name
    },
    {
      name  = "POSTGRES_USER"
      value = module.rds.rds_instance_username
    },
    {
      name  = "POSTGRES_PASSWORD"
      value = module.rds.rds_instance_db_password
    },
    {
      name  = "AZURE_OPENAI_API_KEY"
      value = var.AZURE_OPENAI_API_KEY
    },
    {
      name  = "AZURE_OPENAI_ENDPOINT"
      value = var.AZURE_OPENAI_ENDPOINT
    },
    {
      name  = "OPENAI_API_VERSION"
      value = var.OPENAI_API_VERSION
    },
    {
      name  = "AZURE_OPENAI_DEPLOYMENT_NAME"
      value = var.AZURE_OPENAI_DEPLOYMENT_NAME
    },
    {
      name  = "OPENSEARCH_USER"
      value = var.OPENSEARCH_USER
    },
    {
      name  = "OPENSEARCH_PASSWORD"
      value = var.OPENSEARCH_PASSWORD
    },
    {
      name  = "OPENSEARCH_URL"
      value = var.OPENSEARCH_URL
    },
    {
      name  = "OPENSEARCH_PORT"
      value = var.OPENSEARCH_PORT
    },
    {
      name  = "OPENSEARCH_SCHEME"
      value = var.OPENSEARCH_SCHEME
    },
    {
      name  = "EMBEDDING_MODEL"
      value = var.EMBEDDING_MODEL
    },
    {
      name  = "OPENSEARCH_INDEX"
      value = var.OPENSEARCH_INDEX
    },
    {
      name  = "OPENSEARCH_AWS_REGION"
      value = var.OPENSEARCH_AWS_REGION
    },
    {
      name  = "SENTRY_DSN"
      value = jsonencode(var.SENTRY_DSN)
    },
    {
      name  = "SENTRY_AUTH_TOKEN"
      value = jsonencode(var.SENTRY_AUTH_TOKEN)
    },
    {
      name  = "DISABLE_AUTH_SIGNATURE_VERIFICATION"
      value = var.disable_auth_signature_verification
    },
    {
      name  = "AUTH_PROVIDER_PUBLIC_KEY"
      value = data.aws_ssm_parameter.auth_provider_public_key.value
    },
    {
      name  = "KEYCLOAK_ALLOWED_ROLES"
      value = jsonencode(var.keycloak_allowed_roles)
    },
    {
      name = "RESOURCE_URL_TEMPLATE"
      value = var.RESOURCE_URL_TEMPLATE
    },
    {
      name = "ADMIN_USERS"
      value = var.ADMIN_USERS
    }
  ]
}

resource "aws_ssm_parameter" "env_secrets" {
  for_each = { for ev in local.env_secrets : ev.name => ev }
  
  type   = "SecureString"
  key_id = data.terraform_remote_state.platform.outputs.kms_key_arn

  name  = "/${local.name}/env_secrets/${each.value.name}"
  value = each.value.value

  lifecycle {
    ignore_changes = [
      value,
    ]
  }
}
