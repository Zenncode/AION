# =============================================================================
# VPC
# =============================================================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnets
}

output "nat_gateway_ips" {
  description = "Public IPs of the NAT Gateways"
  value       = module.vpc.nat_public_ips
}

# =============================================================================
# EKS Cluster
# =============================================================================

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = module.eks.cluster_arn
}

output "cluster_certificate_authority" {
  description = "Base64 encoded certificate data for cluster CA"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_oidc_provider_arn" {
  description = "OIDC provider ARN for IRSA"
  value       = module.eks.oidc_provider_arn
}

# =============================================================================
# Kubeconfig
# =============================================================================

output "kubeconfig_command" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}

output "kubeconfig" {
  description = "Kubeconfig content (use with: terraform output -raw kubeconfig > ~/.kube/config)"
  value       = <<KUBECONFIG
apiVersion: v1
kind: Config
preferences: {}
current-context: ${local.name_prefix}-eks

clusters:
- cluster:
    server: ${module.eks.cluster_endpoint}
    certificate-authority-data: ${module.eks.cluster_certificate_authority_data}
  name: ${local.name_prefix}-eks

contexts:
- context:
    cluster: ${local.name_prefix}-eks
    user: ${local.name_prefix}-eks
  name: ${local.name_prefix}-eks

users:
- name: ${local.name_prefix}-eks
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
      - eks
      - get-token
      - --cluster-name
      - ${module.eks.cluster_name}
      - --region
      - ${var.aws_region}
KUBECONFIG
  sensitive = true
}

# =============================================================================
# RDS — PostgreSQL
# =============================================================================

output "rds_cluster_endpoint" {
  description = "RDS cluster writer endpoint"
  value       = aws_rds_cluster.postgres.endpoint
}

output "rds_cluster_reader_endpoint" {
  description = "RDS cluster reader endpoint"
  value       = aws_rds_cluster.postgres.reader_endpoint
}

output "rds_cluster_port" {
  description = "RDS cluster port"
  value       = aws_rds_cluster.postgres.port
}

output "database_name" {
  description = "Database name"
  value       = aws_rds_cluster.postgres.database_name
}

output "database_connection_string" {
  description = "PostgreSQL connection string for direct connection"
  value       = "postgresql://${var.database_master_username}:${var.database_master_password}@${aws_rds_cluster.postgres.endpoint}:5432/${aws_rds_cluster.postgres.database_name}"
  sensitive   = true
}

output "database_connection_string_ssl" {
  description = "PostgreSQL connection string with SSL require"
  value       = "postgresql://${var.database_master_username}:${var.database_master_password}@${aws_rds_cluster.postgres.endpoint}:5432/${aws_rds_cluster.postgres.database_name}?sslmode=require"
  sensitive   = true
}

# =============================================================================
# MSK — Kafka
# =============================================================================

output "msk_cluster_arn" {
  description = "ARN of the MSK cluster"
  value       = module.msk.cluster_arn
}

output "msk_cluster_name" {
  description = "Name of the MSK cluster"
  value       = module.msk.cluster_name
}

output "msk_bootstrap_brokers" {
  description = "MSK bootstrap broker addresses (plaintext)"
  value       = module.msk.bootstrap_brokers
}

output "msk_bootstrap_brokers_tls" {
  description = "MSK bootstrap broker addresses (TLS)"
  value       = module.msk.bootstrap_brokers_tls
}

output "msk_zookeeper_connect_string" {
  description = "MSK ZooKeeper connect string"
  value       = module.msk.zookeeper_connect_string
}

output "kafka_connection_info" {
  description = "Kafka connection details formatted for application use"
  value       = <<EOT
Bootstrap Servers (Plaintext): ${module.msk.bootstrap_brokers}
Bootstrap Servers (TLS):       ${module.msk.bootstrap_brokers_tls}
ZooKeeper:                     ${module.msk.zookeeper_connect_string}
EOT
}

# =============================================================================
# IRSA — IAM Roles
# =============================================================================

output "msk_irsa_role_arn" {
  description = "IAM role ARN for MSK access (IRSA)"
  value       = module.msk_irsa.iam_role_arn
}

output "s3_irsa_role_arn" {
  description = "IAM role ARN for S3 access (IRSA)"
  value       = module.s3_irsa.iam_role_arn
}

output "rds_irsa_role_arn" {
  description = "IAM role ARN for RDS access (IRSA)"
  value       = module.rds_irsa.iam_role_arn
}

output "generic_irsa_role_arn" {
  description = "IAM role ARN for generic AWS API access (IRSA)"
  value       = module.generic_irsa.iam_role_arn
}

output "vpc_cni_irsa_role_arn" {
  description = "IAM role ARN for VPC CNI (IRSA)"
  value       = module.vpc_cni_irsa.iam_role_arn
}

output "ebs_csi_irsa_role_arn" {
  description = "IAM role ARN for EBS CSI driver (IRSA)"
  value       = module.ebs_csi_irsa.iam_role_arn
}

# =============================================================================
# Service Accounts
# =============================================================================

output "kafka_service_account" {
  description = "Kafka service account name and namespace"
  value       = "${kubernetes_service_account.msk_sa.metadata[0].namespace}/${kubernetes_service_account.msk_sa.metadata[0].name}"
}

output "s3_service_account" {
  description = "S3 service account name and namespace"
  value       = "${kubernetes_service_account.s3_sa.metadata[0].namespace}/${kubernetes_service_account.s3_sa.metadata[0].name}"
}

output "rds_service_account" {
  description = "RDS service account name and namespace"
  value       = "${kubernetes_service_account.rds_sa.metadata[0].namespace}/${kubernetes_service_account.rds_sa.metadata[0].name}"
}

output "generic_service_account" {
  description = "Generic service account name and namespace"
  value       = "${kubernetes_service_account.generic_sa.metadata[0].namespace}/${kubernetes_service_account.generic_sa.metadata[0].name}"
}

# =============================================================================
# Quick Start
# =============================================================================

output "next_steps" {
  description = "Post-deployment instructions"
  value       = <<EOT
=== AION Infrastructure Deployed ===

1. Configure kubectl:
   aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}

2. Verify cluster:
   kubectl get nodes
   kubectl get pods -n ${var.namespace}

3. Database:
   Writer endpoint: ${aws_rds_cluster.postgres.endpoint}
   Reader endpoint: ${aws_rds_cluster.postgres.reader_endpoint}

4. Kafka:
   Bootstrap (TLS): ${module.msk.bootstrap_brokers_tls}

5. Use the service accounts with IRSA annotations:
   kubectl get sa -n ${var.namespace} -o yaml
EOT
}
