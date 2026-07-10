terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket         = "aion-terraform-state"
    key            = "eks/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "AION"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# --- Data Sources ---

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix = "aion-${var.environment}"
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)
}

# =============================================================================
# VPC
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tags required by EKS for subnet auto-discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb"                          = 1
    "kubernetes.io/cluster/${local.name_prefix}-eks"  = "owned"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"                 = 1
    "kubernetes.io/cluster/${local.name_prefix}-eks"  = "owned"
  }

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

# =============================================================================
# EKS Cluster
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${local.name_prefix}-eks"
  cluster_version = var.eks_cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # Enable IRSA
  enable_irsa = true

  # Cluster Addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent              = true
      service_account_role_arn = module.vpc_cni_irsa.iam_role_arn
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Access entries
  enable_cluster_creator_admin_permissions = true

  tags = {
    Name = "${local.name_prefix}-eks"
  }
}

# =============================================================================
# EKS Managed Node Groups
# =============================================================================

# Critical system pods — On-Demand
resource "aws_eks_node_group" "system" {
  cluster_name    = module.eks.cluster_name
  node_group_name = "${local.name_prefix}-system"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = module.vpc.private_subnets

  capacity_type  = "ON_DEMAND"
  instance_types = var.system_instance_types

  scaling_config {
    desired_size = var.system_desired_size
    min_size     = var.system_min_size
    max_size     = var.system_max_size
  }

  labels = {
    role        = "system"
    capacity    = "on-demand"
    node_group  = "system"
  }

  taint {
    key    = "CriticalAddonsOnly"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name = "${local.name_prefix}-system-nodes"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.node_AmazonEKS_CNI_Policy,
    aws_iam_role_policy_attachment.node_AmazonEC2ContainerRegistryReadOnly,
    aws_iam_role_policy_attachment.node_AmazonSSMManagedInstanceCore,
  ]
}

# Worker nodes — Spot instances
resource "aws_eks_node_group" "workers" {
  cluster_name    = module.eks.cluster_name
  node_group_name = "${local.name_prefix}-workers"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = module.vpc.private_subnets

  capacity_type  = "SPOT"
  instance_types = var.worker_instance_types

  scaling_config {
    desired_size = var.worker_desired_size
    min_size     = var.worker_min_size
    max_size     = var.worker_max_size
  }

  labels = {
    role        = "worker"
    capacity    = "spot"
    node_group  = "workers"
  }

  update_config {
    max_unavailable_percentage = 25
  }

  tags = {
    Name = "${local.name_prefix}-worker-nodes"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.node_AmazonEKS_CNI_Policy,
    aws_iam_role_policy_attachment.node_AmazonEC2ContainerRegistryReadOnly,
    aws_iam_role_policy_attachment.node_AmazonSSMManagedInstanceCore,
  ]
}

# =============================================================================
# IAM — Node Group Role
# =============================================================================

resource "aws_iam_role" "node" {
  name = "${local.name_prefix}-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "node_AmazonEKSWorkerNodePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonEKS_CNI_Policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonEC2ContainerRegistryReadOnly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonSSMManagedInstanceCore" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.node.name
}

# =============================================================================
# IRSA — VPC CNI
# =============================================================================

module "vpc_cni_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name_prefix}-vpc-cni"
  attach_vpc_cni_policy = true
  vpc_cni_enable_ipv4   = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-node"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-vpc-cni-irsa"
  }
}

# =============================================================================
# IRSA — EBS CSI Driver
# =============================================================================

module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name_prefix}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-ebs-csi-irsa"
  }
}

# =============================================================================
# IRSA — Kafka MSK Access (for application pods)
# =============================================================================

module "msk_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name_prefix}-msk-access"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["${var.namespace}:${var.mks_service_account_name}"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-msk-irsa"
  }
}

resource "aws_iam_role_policy" "msk_access" {
  name = "${local.name_prefix}-msk-access-policy"
  role = module.msk_irsa.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeGroup",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:DescribeTopicDynamicConfiguration",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:DescribeClusterDynamicConfiguration",
          "kafka-cluster:AlterGroup",
        ]
        Resource = [
          module.msk.cluster_arn,
          "${module.msk.cluster_arn}/*"
        ]
      }
    ]
  })
}

# =============================================================================
# IRSA — S3 Access (application pods)
# =============================================================================

module "s3_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name_prefix}-s3-access"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["${var.namespace}:${var.s3_service_account_name}"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-s3-irsa"
  }
}

resource "aws_iam_role_policy" "s3_access" {
  name = "${local.name_prefix}-s3-access-policy"
  role = module.s3_irsa.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject",
        ]
        Resource = [
          "arn:aws:s3:::${local.name_prefix}-*",
          "arn:aws:s3:::${local.name_prefix}-*/*"
        ]
      }
    ]
  })
}

# =============================================================================
# AWS RDS — PostgreSQL
# =============================================================================

resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name_prefix}-postgres"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "${local.name_prefix}-postgres-subnet-group"
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.name_prefix}-rds-"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "PostgreSQL from EKS VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-rds-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${local.name_prefix}-postgres-${var.rds_engine_version}"
  family = "postgres${split(".", var.rds_engine_version)[0]}"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_checkpoints"
    value = "1"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  tags = {
    Name = "${local.name_prefix}-postgres-params"
  }
}

resource "aws_rds_cluster" "postgres" {
  cluster_identifier     = "${local.name_prefix}-postgres"
  engine                 = "aurora-postgresql"
  engine_version         = var.rds_engine_version
  database_name          = var.database_name
  master_username        = var.database_master_username
  master_password        = var.database_master_password
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_cluster_parameter_group_name = aws_db_parameter_group.postgres.name
  storage_encrypted      = true
  skip_final_snapshot    = var.environment != "production"
  deletion_protection    = var.environment == "production"
  backup_retention_period = var.environment == "production" ? 14 : 7

  tags = {
    Name = "${local.name_prefix}-postgres-cluster"
  }
}

resource "aws_rds_cluster_instance" "postgres" {
  count              = var.environment == "production" ? 2 : 1
  identifier         = "${local.name_prefix}-postgres-${count.index}"
  cluster_identifier = aws_rds_cluster.postgres.id
  instance_class     = var.rds_instance_class
  engine             = aws_rds_cluster.postgres.engine
  engine_version     = aws_rds_cluster.postgres.engine_version

  performance_insights_enabled = true

  tags = {
    Name = "${local.name_prefix}-postgres-instance-${count.index}"
  }
}

# =============================================================================
# AWS MSK — Managed Kafka
# =============================================================================

resource "aws_security_group" "msk" {
  name_prefix = "${local.name_prefix}-msk-"
  description = "Security group for MSK cluster"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "Kafka broker plaintext"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "Kafka broker TLS"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "MSK SCRAM"
    from_port   = 9096
    to_port     = 9096
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-msk-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

module "msk" {
  source  = "terraform-aws-modules/msk/aws"
  version = "~> 2.0"

  name                   = "${local.name_prefix}-msk"
  kafka_version          = var.msk_kafka_version
  number_of_broker_nodes = var.msk_broker_count

  broker_node_group_info = {
    instance_type   = var.msk_instance_type
    storage_info = {
      ebs_storage_info = {
        volume_size = var.msk_volume_size
      }
    }
    client_subnets = slice(module.vpc.private_subnets, 0, var.msk_broker_count)
    security_groups = [aws_security_group.msk.id]
  }

  encryption_info = {
    encryption_in_transit = {
      client_broker = "TLS"
      in_cluster    = true
    }
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
  }

  configuration_info = {
    arn      = aws_msk_configuration.kafka.arn
    revision = aws_msk_configuration.kafka.latest_revision
  }

  logging_info = {
    broker_logs = {
      cloudwatch_logs = {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  tags = {
    Name = "${local.name_prefix}-msk"
  }
}

resource "aws_kms_key" "msk" {
  description             = "MSK encryption key for ${local.name_prefix}"
  deletion_window_in_days = 7

  tags = {
    Name = "${local.name_prefix}-msk-kms"
  }
}

resource "aws_kms_alias" "msk" {
  name          = "alias/${local.name_prefix}-msk"
  target_key_id = aws_kms_key.msk.key_id
}

resource "aws_msk_configuration" "kafka" {
  name              = "${local.name_prefix}-kafka-config"
  kafka_version    = var.msk_kafka_version
  number_of_broker_nodes = var.msk_broker_count

  broker_node_group_info {
    instance_type  = var.msk_instance_type
    storage_info {
      ebs_storage_info {
        volume_size = var.msk_volume_size
      }
    }
  }

  server_properties = <<PROPERTIES
auto.create.topics.enable=true
default.replication.factor=3
min.insync.replicas=2
num.partitions=3
log.retention.hours=168
PROPERTIES

  tags = {
    Name = "${local.name_prefix}-kafka-config"
  }
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/msk/${local.name_prefix}-msk"
  retention_in_days = 14

  tags = {
    Name = "${local.name_prefix}-msk-logs"
  }
}

# =============================================================================
# IAM — IRSA for RDS Metadata Access
# =============================================================================

module "rds_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name_prefix}-rds-access"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["${var.namespace}:${var.rds_service_account_name}"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-rds-irsa"
  }
}

# =============================================================================
# Kubernetes Provider
# =============================================================================

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# =============================================================================
# Namespace & Service Account IRSA Bindings
# =============================================================================

resource "kubernetes_namespace" "aion" {
  metadata {
    name = var.namespace
    labels = {
      name        = var.namespace
      environment = var.environment
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_service_account" "msk_sa" {
  metadata {
    name      = var.mks_service_account_name
    namespace = kubernetes_namespace.aion.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = module.msk_irsa.iam_role_arn
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_service_account" "s3_sa" {
  metadata {
    name      = var.s3_service_account_name
    namespace = kubernetes_namespace.aion.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = module.s3_irsa.iam_role_arn
    }
  }

  depends_on = [module.eks]
}

resource "kubernetes_service_account" "rds_sa" {
  metadata {
    name      = var.rds_service_account_name
    namespace = kubernetes_namespace.aion.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = module.rds_irsa.iam_role_arn
    }
  }

  depends_on = [module.eks]
}

# =============================================================================
# IRSA Service Account for Pod-level AWS API access (generic)
# =============================================================================

module "generic_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name_prefix}-generic-access"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["${var.namespace}:${var.generic_service_account_name}"]
    }
  }

  tags = {
    Name = "${local.name_prefix}-generic-irsa"
  }
}

resource "kubernetes_service_account" "generic_sa" {
  metadata {
    name      = var.generic_service_account_name
    namespace = kubernetes_namespace.aion.metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = module.generic_irsa.iam_role_arn
    }
  }

  depends_on = [module.eks]
}
