locals {
  app_name    = var.app_name
  environment = var.environment
}

data "aws_caller_identity" "main" {}

resource "aws_iam_role" "admin" {
  name = "${local.environment}-${local.app_name}-admin"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.main.account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${local.environment}-${local.app_name}-admin"
    Environment = local.environment
    Application = local.app_name
  }
}

resource "aws_iam_role_policy_attachment" "admin_policy" {
  role       = aws_iam_role.admin.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
