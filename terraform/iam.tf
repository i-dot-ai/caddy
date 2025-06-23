data "aws_iam_policy_document" "ecs_exec_custom_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:*",
    ]
    resources = [
      module.app_bucket.arn,
      "${module.app_bucket.arn}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:ListAllMyBuckets",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]
    resources = [
      "arn:aws:ssm:*:${data.aws_caller_identity.current.account_id}:parameter/${local.name}/env_secrets/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]
    resources = [
      data.terraform_remote_state.platform.outputs.kms_key_arn,
      "${module.app_bucket.arn}"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "es:*"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "bedrock:Invoke*"
    ]
    resources = [
      "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "opensearch:*"
    ]
    resources = [
      "arn:aws:opensearch:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:datasource/*",
      "arn:aws:opensearch:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:application/*"
    ]
  }
}

resource "aws_iam_policy" "ecs_exec_custom_policy" {
  name        = "${local.name}-ecs-custom-exec"
  description = "ECS task custom policy"
  policy      = data.aws_iam_policy_document.ecs_exec_custom_policy.json
}
