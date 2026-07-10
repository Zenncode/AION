# =============================================================================
# General
# =============================================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  default     = "development"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "namespace" {
  description = "Kubernetes namespace for AION services"
  type        = string
  default     = "aion"
}

# =============================================================================
# VPC
# =============================================================================

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

# =============================================================================
# EKS
# =============================================================================

variable "eks_cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

# System node group — On-Demand
variable "system_instance_types" {
  description = "Instance types for the system (On-Demand) node group"
  type        = list(string)
  default     = ["m6i.xlarge", "m6i.2xlarge"]
}

variable "system_desired_size" {
  description = "Desired number of system nodes"
  type        = number
  default     = 2
}

variable "system_min_size" {
  description = "Minimum number of system nodes"
  type        = number
  default     = 2
}

variable "system_max_size" {
  description = "Maximum number of system nodes"
  type        = number
  default     = 4
}

# Worker node group — Spot
variable "worker_instance_types" {
  description = "Instance types for the worker (Spot) node group"
  type        = list(string)
  default     = ["m6i.xlarge", "m6i.2xlarge", "m5.xlarge", "m5.2xlarge", "c6i.xlarge", "c6i.2xlarge"]
}

variable "worker_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 3
}

variable "worker_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "worker_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 10
}

# =============================================================================
# IAM Role for Service Accounts — Service Account Names
# =============================================================================

variable "mks_service_account_name" {
  description = "Kubernetes service account name for MSK access"
  type        = string
  default     = "aion-kafka"
}

variable "s3_service_account_name" {
  description = "Kubernetes service account name for S3 access"
  type        = string
  default     = "aion-s3"
}

variable "rds_service_account_name" {
  description = "Kubernetes service account name for RDS access"
  type        = string
  default     = "aion-rds"
}

variable "generic_service_account_name" {
  description = "Kubernetes service account name for generic AWS API access"
  type        = string
  default     = "aion-generic"
}

# =============================================================================
# RDS — PostgreSQL
# =============================================================================

variable "rds_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "database_name" {
  description = "Name of the initial database"
  type        = string
  default     = "aion"
}

variable "database_master_username" {
  description = "Master username for the database"
  type        = string
  default     = "aion_admin"
  sensitive   = true
}

variable "database_master_password" {
  description = "Master password for the database"
  type        = string
  sensitive   = true
}

# =============================================================================
# MSK — Kafka
# =============================================================================

variable "msk_kafka_version" {
  description = "Kafka version for MSK"
  type        = string
  default     = "3.5.1"
}

variable "msk_broker_count" {
  description = "Number of MSK broker nodes"
  type        = number
  default     = 3

  validation {
    condition     = var.msk_broker_count >= 3
    error_message = "MSK requires at least 3 brokers for multi-AZ."
  }
}

variable "msk_instance_type" {
  description = "MSK broker instance type"
  type        = string
  default     = "kafka.m5.large"
}

variable "msk_volume_size" {
  description = "EBS volume size per broker in GB"
  type        = number
  default     = 100
}
