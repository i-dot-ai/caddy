locals {
  backend_port  = 8080
  frontend_port  = 8081
  additional_policy_arns = {for idx, arn in [aws_iam_policy.ecs_exec_custom_policy.arn] : idx => arn}
  slack_webhook          = var.slack_webhook
}

data "aws_lb_listener" "lb_listener_443" {
  load_balancer_arn = module.load_balancer.alb_arn
  port              = 443
}


module "model" {
  name = "${local.name}-model"
  # checkov:skip=CKV_SECRET_4:Skip secret check as these have to be used within the Github Action
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  #source                      = "../../i-dot-ai-core-terraform-modules//modules/infrastructure/ecs" # For testing local changes
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/infrastructure/ecs?ref=v5.3.0-ecs"
  image_tag                    = var.image_tag
  ecr_repository_uri           = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com/caddy-model"
  vpc_id                       = data.terraform_remote_state.vpc.outputs.vpc_id
  private_subnets              = data.terraform_remote_state.vpc.outputs.private_subnets
  host                         = local.host_backend
  load_balancer_security_group = module.load_balancer.load_balancer_security_group_id
  aws_lb_arn                   = module.load_balancer.alb_arn
  ecs_cluster_id               = data.terraform_remote_state.platform.outputs.ecs_cluster_id
  ecs_cluster_name             = data.terraform_remote_state.platform.outputs.ecs_cluster_name
  https_listener_arn           = data.aws_lb_listener.lb_listener_443.arn
  task_additional_iam_policies = local.additional_policy_arns
  certificate_arn              = data.terraform_remote_state.universal.outputs.certificate_arn
  target_group_name_override   =  "caddy-mo-${var.env}-tg"
  permissions_boundary_name    = "infra/i-dot-ai-${var.env}-caddy-perms-boundary-app"

  
  service_discovery_service_arn = aws_service_discovery_service.service_discovery_service.arn
  create_networking = true
  create_listener   = false

  additional_security_group_ingress = [
    {
      purpose          = "Frontend to backend container port"
      port             = local.backend_port
      additional_sg_id = module.frontend.ecs_sg_id
    }
  ]
  

  environment_variables = {
    "ENVIRONMENT" : terraform.workspace,
    "APP_NAME" : "${local.name}-model"
    "PORT" : local.backend_port,
    "REPO" : "caddy",
    "AWS_ACCOUNT_ID": var.account_id,
 
  }

  secrets = [
    for k, v in aws_ssm_parameter.env_secrets : {
      name = regex("([^/]+$)", v.arn)[0], # Extract right-most string (param name) after the final slash
      valueFrom = v.arn
    }
  ]

  container_port             = local.backend_port
  memory                     = terraform.workspace == "prod" ? 2048 : 1024
  cpu                        = terraform.workspace == "prod" ? 1024 : 512
  autoscaling_maximum_target = var.env == "prod" ? 5 : 1

  health_check = {
    accepted_response   = 200
    path                = "/healthcheck"
    interval            = 60
    timeout             = 70
    healthy_threshold   = 2
    unhealthy_threshold = 5
    port                = local.backend_port
  }
}

module "frontend" {
  # checkov:skip=CKV_SECRET_4:Skip secret check as these have to be used within the Github Action
  name = "${local.name}-frontend"
  # source = "../../i-dot-ai-core-terraform-modules//modules/infrastructure/ecs" # For testing local changes
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/infrastructure/ecs?ref=v5.3.0-ecs"
  image_tag                    = var.image_tag
  ecr_repository_uri           = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com/caddy-frontend"
  vpc_id                       = data.terraform_remote_state.vpc.outputs.vpc_id
  private_subnets              = data.terraform_remote_state.vpc.outputs.private_subnets
  host                         = local.host
  load_balancer_security_group = module.load_balancer.load_balancer_security_group_id
  aws_lb_arn                   = module.load_balancer.alb_arn
  ecs_cluster_id               = data.terraform_remote_state.platform.outputs.ecs_cluster_id
  ecs_cluster_name             = data.terraform_remote_state.platform.outputs.ecs_cluster_name
  create_listener              = true
  certificate_arn              = data.terraform_remote_state.universal.outputs.certificate_arn
  target_group_name_override   = "caddy-fe-${var.env}-tg"
  task_additional_iam_policies = local.additional_policy_arns
  permissions_boundary_name    = "infra/i-dot-ai-${var.env}-caddy-perms-boundary-app"

  environment_variables = {
    "ENVIRONMENT" : terraform.workspace,
    "APP_NAME" : "${local.name}-frontend"
    "PORT" : local.frontend_port,
    "REPO" : "caddy",
    "BACKEND_HOST" : "http://${aws_service_discovery_service.service_discovery_service.name}.${aws_service_discovery_private_dns_namespace.private_dns_namespace.name}:${local.backend_port}"
  }

  secrets = [
    for k, v in aws_ssm_parameter.env_secrets : {
      name      = regex("([^/]+$)", v.arn)[0], # Extract right-most string (param name) after the final slash
      valueFrom = v.arn
    }
  ]

  container_port             = local.frontend_port
  memory                     = terraform.workspace == "prod" ? 2048 : 1024
  cpu                        = terraform.workspace == "prod" ? 1024 : 512
  autoscaling_maximum_target = var.env == "prod" ? 5 : 1

  health_check = {
    accepted_response   = 200
    path                = "/api/health"
    interval            = 60
    timeout             = 70
    healthy_threshold   = 2
    unhealthy_threshold = 5
    port                = local.frontend_port
  }

  authenticate_keycloak = {
    enabled : true,
    realm_name : data.terraform_remote_state.keycloak.outputs.realm_name,
    client_id : var.project_name,
    client_secret : data.aws_ssm_parameter.client_secret.value,
    keycloak_dns : data.terraform_remote_state.keycloak.outputs.keycloak_dns
  }
}

resource "aws_service_discovery_private_dns_namespace" "private_dns_namespace" {
  name        = "${local.name}-internal"
  description = "${local.name} private dns namespace"
  vpc         = data.terraform_remote_state.vpc.outputs.vpc_id
}

resource "aws_service_discovery_service" "service_discovery_service" {
  name = "${local.name}-backend"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.private_dns_namespace.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

module "sns_topic" {
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  # source                       = "../../i-dot-ai-core-terraform-modules/modules/observability/cloudwatch-slack-integration"
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/observability/cloudwatch-slack-integration?ref=v2.0.1-cloudwatch-slack-integration"
  name                         = local.name
  slack_webhook                = data.aws_secretsmanager_secret_version.platform_slack_webhook.secret_string

  permissions_boundary_name    = "infra/i-dot-ai-${var.env}-caddy-perms-boundary-app"
}

module "model-ecs-alarm" {
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  # source                       = "../../i-dot-ai-core-terraform-modules/modules/observability/ecs-alarms"
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/observability/ecs-alarms?ref=v1.0.1-ecs-alarms"
  name                         = "${local.name}-model"
  ecs_service_name             = module.model.ecs_service_name
  ecs_cluster_name             = data.terraform_remote_state.platform.outputs.ecs_cluster_name
  sns_topic_arn                = [module.sns_topic.sns_topic_arn]
}
module "model-alb-alarm" {
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  # source                       = "../../i-dot-ai-core-terraform-modules/modules/observability/alb-alarms"
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/observability/alb-alarms?ref=v1.1.0-alb-alarms"
  name                         = "${local.name}-model"
  alb_arn                      = module.load_balancer.alb_arn
  target_group                 = module.model.aws_lb_target_group_name
  sns_topic_arn                = [module.sns_topic.sns_topic_arn]

  high_request_count_threshold = 100
}