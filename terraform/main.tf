terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      projeto  = "oficina"
      ambiente = var.env
    }
  }
}

locals {
  prefixo = "oficina-${var.env}"
}

data "aws_caller_identity" "atual" {}

data "aws_ssm_parameter" "cluster_name" {
  name = "/oficina/eks/cluster_name"
}

resource "aws_sqs_queue" "eventos_dlq" {
  name                      = "${local.prefixo}-os-eventos-dlq.fifo"
  fifo_queue                = true
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "eventos" {
  name                        = "${local.prefixo}-os-eventos.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.eventos_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_iam_role" "worker" {
  name = "${local.prefixo}-os-worker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy" "worker" {
  name = "acesso-os-worker"
  role = aws_iam_role.worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueUrl", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.eventos.arn
      },
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:GetQueueUrl"]
        Resource = [
          "arn:aws:sqs:${var.region}:${data.aws_caller_identity.atual.account_id}:${local.prefixo}-billing-comandos.fifo",
          "arn:aws:sqs:${var.region}:${data.aws_caller_identity.atual.account_id}:${local.prefixo}-execucao-comandos.fifo"
        ]
      }
    ]
  })
}

resource "aws_eks_pod_identity_association" "worker" {
  cluster_name    = data.aws_ssm_parameter.cluster_name.value
  namespace       = var.env
  service_account = "oficina-worker"
  role_arn        = aws_iam_role.worker.arn
}
