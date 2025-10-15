locals {
  qdrant_port = 6333
}

# Qdrant service using the same ECS module pattern as backend
module "qdrant" {
  name = "${local.name}-qdrant"
  # checkov:skip=CKV_SECRET_4:Skip secret check as these have to be used within the Github Action
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  #source                      = "../../i-dot-ai-core-terraform-modules//modules/infrastructure/ecs" # For testing local changes
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/infrastructure/ecs?ref=v5.4.1-ecs"

  image_tag                    = "latest"
  ecr_repository_uri           = "qdrant/qdrant"

  vpc_id                       = data.terraform_remote_state.vpc.outputs.vpc_id
  private_subnets              = data.terraform_remote_state.vpc.outputs.private_subnets
  host                         = local.host_qdrant
  load_balancer_security_group = module.load_balancer.load_balancer_security_group_id
  aws_lb_arn                   = module.load_balancer.alb_arn
  ecs_cluster_id               = data.terraform_remote_state.platform.outputs.ecs_cluster_id
  ecs_cluster_name             = data.terraform_remote_state.platform.outputs.ecs_cluster_name
  https_listener_arn           = data.aws_lb_listener.lb_listener_443.arn
  certificate_arn              = data.terraform_remote_state.universal.outputs.certificate_arn
  target_group_name_override   = "caddy-qdrant-${var.env}-tg"
  permissions_boundary_name    = "infra/i-dot-ai-${var.env}-caddy-perms-boundary-app"
  container_port               = local.qdrant_port

  service_discovery_service_arn = aws_service_discovery_service.service_discovery_service.arn
  create_networking = true
  create_listener = false

  memory = 4096
  cpu    = 2048

  additional_security_group_ingress = [
    {
      purpose          = "Backend to qdrant container port"
      port             = local.qdrant_port
      additional_sg_id = module.model.ecs_sg_id
    }
  ]

  desired_app_count          = 1
  autoscaling_minimum_target = 1
  autoscaling_maximum_target = 1

  environment_variables = {
    "QDRANT_URL" = "http://${aws_service_discovery_service.service_discovery_service.name}.${aws_service_discovery_private_dns_namespace.private_dns_namespace.name}:${local.qdrant_port}"
    "QDRANT__LOG_LEVEL" = terraform.workspace == "prod" ? "warn" : "info"
    "QDRANT__SERVICE__HTTP_PORT" = tostring(local.qdrant_port)
    "QDRANT__SERVICE__ENABLE_HTTPS" = true
    "QDRANT__SERVICE__ENABLE_CORS" = true
    "QDRANT__SERVICE__CERT" = "./tls/cert.pem"
    "QDRANT__SERVICE__KEY" = "./tls/key.pem"

    "QDRANT__STORAGE__OPTIMIZERS__MEMMAP_THRESHOLD_KB" = "100000"  # Enable memmap for segments >100MB
    "QDRANT__STORAGE__OPTIMIZERS__INDEXING_THRESHOLD_KB" = "100000"  # Index segments >100MB
    "QDRANT__STORAGE__OPTIMIZERS__MAX_SEGMENT_SIZE_KB" = "5000000"  # 5GB max segment size
    "QDRANT__STORAGE__OPTIMIZERS__MAX_OPTIMIZATION_THREADS" = "2"  # Optimization parallelism

    "QDRANT__STORAGE__HNSW_INDEX__M" = "32"  # Increased for better recall at scale
    "QDRANT__STORAGE__HNSW_INDEX__EF_CONSTRUCT" = "400"  # Higher for better index quality
    "QDRANT__STORAGE__HNSW_INDEX__FULL_SCAN_THRESHOLD_KB" = "50000"  # Increased threshold (KB)
    "QDRANT__STORAGE__HNSW_INDEX__MAX_INDEXING_THREADS" = "2"  # Parallel indexing threads

    "QDRANT__PERFORMANCE__MAX_SEARCH_THREADS" = "4"  # Search parallelism

    "QDRANT__SERVICE__MAX_REQUEST_SIZE_MB" = "64"  # 64MB for batch operations
  }

  efs_mount_configuration = [
    {
      file_system_id  = aws_efs_file_system.qdrant.id
      container_path  = "/qdrant/storage"
      access_point_id = aws_efs_access_point.qdrant.id
    }
  ]

  health_check = {
    accepted_response   = 200
    path                = "/healthz"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    port                = local.qdrant_port
  }
}

module "qdrant-ecs-alarm" {
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/observability/ecs-alarms?ref=v1.0.1-ecs-alarms"
  name                         = "${local.name}-qdrant"
  ecs_service_name             = module.qdrant.ecs_service_name
  ecs_cluster_name             = data.terraform_remote_state.platform.outputs.ecs_cluster_name
  sns_topic_arn                = [module.sns_topic.sns_topic_arn]
}

module "qdrant-alb-alarm" {
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  source                       = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/observability/alb-alarms?ref=v1.0.0-alb-alarms"
  name                         = "${local.name}-qdrant"
  alb_arn                      = module.load_balancer.alb_arn
  target_group                 = module.qdrant.aws_lb_target_group_name
  sns_topic_arn                = [module.sns_topic.sns_topic_arn]
}
