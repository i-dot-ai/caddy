variable "account_id" {
  type        = string
  description = "The AWS account ID"
}

variable "AZURE_OPENAI_API_KEY" {
  type        = string
  description = "Azure openai API key"
  sensitive   = true
}

variable "AZURE_OPENAI_DEPLOYMENT_NAME" {
  type        = string
  description = "Azure openai deployment name"
  sensitive   = true
}

variable "AZURE_OPENAI_ENDPOINT" {
  type        = string
  description = "Azure openai endpoint url"
  sensitive   = true
}

variable "deployed_via" {
  type        = string
  default     = "GitHub_Actions"
  description = "Mechanism for how the Infra was deployed."
}

variable "developer_ips" {
  type        = list(string)
  default     = []
  description = "The developer IPs allowed RDS access"
}

variable "domain_name" {
  type        = string
  description = "The base domain name for the project"
}

variable "EMBEDDING_MODEL" {
  type        = string
  description = "Azure openai API key"
  sensitive   = true
}

variable "env" {
  type        = string
  description = "environment"
  default     = "dev"
}

variable "github_org" {
  type        = string
  default     = "github.com/i-dot-ai/"
  description = "The default I.AI GitHub Org URL"
}

variable "hosted_zone_id" {
  type        = string
  description = "Route 53 Hosted Zone"
  sensitive   = true
}

variable "image_tag" {
  description = "The tag of the image to use"
  type        = string
  default     = "latest"
}

variable "OPENAI_API_VERSION" {
  type = string
  description = "Azure openai version"
  sensitive = true
}

variable "OPENSEARCH_AWS_REGION" {
  type = string
  description = "Opensearch region"
  sensitive = true
}

variable "OPENSEARCH_INDEX" {
  type = string
  description = "Opensearch index"
  sensitive = true
}

variable "OPENSEARCH_PASSWORD" {
  type = string
  description = "Opensearch password"
  sensitive = true
}

variable "OPENSEARCH_PORT" {
  type = string
  description = "Opensearch port"
  sensitive = true
}

variable "OPENSEARCH_SCHEME" {
  type = string
  description = "Opensearch http(s) scheme"
  sensitive = true
}

variable "OPENSEARCH_URL" {
  type = string
  description = "Opensearch url (without http(s) scheme)"
  sensitive = true
}

variable "OPENSEARCH_USER" {
  type = string
  description = "Opensearch user"
  sensitive = true
}

variable "project_name" {
  type        = string
  description = "Name of project"
}

variable "region" {
  type        = string
  description = "AWS region for infrastructure to be deployed to"
}

variable "repository_name" {
  type        = string
  description = "The GitHub repository name"
}

variable "security_level" {
  type        = string
  default     = "base"
  description = "Security Level of the infrastructure."
}

variable "SENTRY_DSN" {
  type        = string
  description = "DSN to use to send telemetry to sentry."
  sensitive   = true
}

variable "SENTRY_AUTH_TOKEN" {
  type        = string
  description = "Auth token used by sentry astro config."
  sensitive   = true
}

variable "slack_webhook" {
  type        = string
  description = "Slack webook URL for alert."
  sensitive   = true
}

variable "state_bucket" {
  type        = string
  description = "Name of the S3 bucket to use a terraform state"
}

variable "team_name" {
  type        = string
  description = "The name of the team"
}

variable "universal_tags" {
  type        = map(string)
  description = "Map to tag resources with"
}

variable "BACKEND_TOKEN" {
  type        = string
  sensitive   = true
  description = "Token to connect backend to frontend"
}

variable "disable_auth_signature_verification" {
  type = bool
  default = false
  description = "should auth signature be disabled"
}

variable "keycloak_allowed_roles" {
  type = list(string)
  default = []
  description = "allowed keycloak roles"
}

variable "OPENSEARCH_ADMIN_EMAILS" {
  type = list(string)
  default = []
  description = "admin emails for opensearch"
}

variable "RESOURCE_URL_TEMPLATE" {
  type        = string
  description = "resource url template"
}

variable "ADMIN_USERS" {
  type        = string
  description = "comma seperated list of users email addresses to make admins"
}

variable "scope" {
  description = "Scope of the WAF, either 'CLOUDFRONT' or 'REGIONAL'"
  type        = string
  default     = "REGIONAL"
}
