# AION — Project Context

## 1. Overview

AION is a cloud-native event-driven platform deployed on AWS. It uses Kubernetes for compute, PostgreSQL for persistent metadata, and Kafka for real-time event streaming. Infrastructure is managed entirely through Terraform.

## 2. Architecture

```
                        ┌─────────────────────────────────────┐
                        │             VPC 10.0.0.0/16         │
                        │  eu-west-1 (3 AZs)                  │
                        │                                     │
  Internet ──── NAT ────┤  ┌─────────────────────────────┐    │
              Gateway   │  │      Private Subnets         │    │
                        │  │  ┌──────────────────────┐   │    │
                        │  │  │   EKS Cluster 1.29   │   │    │
                        │  │  │                      │   │    │
                        │  │  │  ┌────────┐ ┌──────┐ │   │    │
                        │  │  │  │ System │ │Worker│ │   │    │
                        │  │  │  │  OD    │ │ Spot │ │   │    │
                        │  │  │  └────────┘ └──────┘ │   │    │
                        │  │  │       │       │      │   │    │
                        │  │  │    IRSA ←→ IAM Roles│   │    │
                        │  │  └───────┼───────┼──────┘   │    │
                        │  │          │       │          │    │
                        │  │  ┌───────┴───────┴──────┐   │    │
                        │  │  │                      │   │    │
                        │  │  │  RDS Aurora PG 15.4  │   │    │
                        │  │  │  MSK Kafka 3.5.1     │   │    │
                        │  │  └──────────────────────┘   │    │
                        │  └─────────────────────────────┘    │
                        │                                     │
                        │  ┌─────────────────────────────┐    │
                        │  │      Public Subnets          │    │
                        │  │  (ALB, NAT GW, Bastion)     │    │
                        │  └─────────────────────────────┘    │
                        └─────────────────────────────────────┘
```

## 3. Infrastructure Components

### 3.1 VPC

| Property        | Value                                    |
|-----------------|------------------------------------------|
| CIDR            | `10.0.0.0/16`                           |
| AZs             | 3 (auto-selected from eu-west-1)        |
| Private subnets | `10.0.1.0/24`, `10.0.2.0/24`, `10.0.3.0/24` |
| Public subnets  | `10.0.101.0/24`, `10.0.102.0/24`, `10.0.103.0/24` |
| NAT Gateway     | Single in non-production; per-AZ in production |
| DNS             | Hostnames + support enabled             |

Subnet tags for EKS auto-discovery:
- Public: `kubernetes.io/role/elb = 1`
- Private: `kubernetes.io/role/internal-elb = 1`
- Both: `kubernetes.io/cluster/<name> = owned`

### 3.2 EKS Cluster

| Property          | Value                     |
|-------------------|---------------------------|
| Name              | `aion-<env>-eks`         |
| Version           | 1.29                      |
| Endpoint access   | Public + Private          |
| IRSA              | Enabled                   |
| OIDC provider     | Auto-provisioned          |

**Addons:**
- CoreDNS (latest)
- kube-proxy (latest)
- VPC CNI (latest, with IRSA)
- EBS CSI Driver (latest, with IRSA)

### 3.3 Node Groups

#### System (On-Demand)

| Property       | Value                              |
|----------------|------------------------------------|
| Capacity       | `ON_DEMAND`                        |
| Instances      | `m6i.xlarge`, `m6i.2xlarge`      |
| Desired        | 2                                  |
| Min / Max      | 2 / 4                              |
| Labels         | `role=system`, `capacity=on-demand`|
| Taint          | `CriticalAddonsOnly=true:NoSchedule`|

Purpose: CoreDNS, kube-proxy, monitoring agents, system operators.

#### Workers (Spot)

| Property       | Value                                         |
|----------------|-----------------------------------------------|
| Capacity       | `SPOT`                                        |
| Instances      | `m6i.xlarge`, `m6i.2xlarge`, `m5.xlarge`, `m5.2xlarge`, `c6i.xlarge`, `c6i.2xlarge` |
| Desired        | 3                                              |
| Min / Max      | 2 / 10                                         |
| Labels         | `role=worker`, `capacity=spot`                 |

Purpose: Application workloads, batch jobs, stateless services.

### 3.4 RDS — Aurora PostgreSQL

| Property              | Value                              |
|-----------------------|------------------------------------|
| Engine                | `aurora-postgresql`                |
| Version               | 15.4                               |
| Instance class        | `db.r6g.large`                     |
| Multi-AZ              | Yes (2 instances in prod, 1 otherwise) |
| Storage encryption    | Enabled (AWS-managed key)          |
| Performance insights  | Enabled                            |
| Deletion protection   | Production only                    |
| Backup retention      | 14 days (prod), 7 days (other)    |
| Parameter group       | `log_connections`, `log_disconnections`, `log_checkpoints`, `pg_stat_statements` |

**Endpoints:**
- Writer: `<cluster>.cluster-<id>.eu-west-1.rds.amazonaws.com:5432`
- Reader: `<cluster>.cluster-ro-<id>.eu-west-1.rds.amazonaws.com:5432`
- Connection string: `postgresql://<user>:<pass>@<writer>:5432/aion?sslmode=require`

### 3.5 MSK — Managed Kafka

| Property              | Value                              |
|-----------------------|------------------------------------|
| Kafka version         | 3.5.1                              |
| Brokers               | 3 (one per AZ)                     |
| Instance type         | `kafka.m5.large`                   |
| EBS volume per broker | 100 GB                             |
| Encryption in transit | TLS (required)                     |
| Encryption at rest    | KMS (custom key)                   |
| Logging               | CloudWatch (`/msk/aion-<env>-msk`)|
| Auto-create topics    | Enabled                            |
| Replication factor    | 3                                  |
| Min ISR               | 2                                  |

**Server properties:**
```
auto.create.topics.enable=true
default.replication.factor=3
min.insync.replicas=2
num.partitions=3
log.retention.hours=168
```

**Endpoints:**
- Plaintext: `<broker1>:9092,<broker2>:9092,<broker3>:9092`
- TLS: `<broker1>:9094,<broker2>:9094,<broker3>:9094`

### 3.6 Security Groups

| Group         | Inbound                          | Outbound |
|---------------|----------------------------------|----------|
| RDS           | TCP 5432 from VPC CIDR           | All      |
| MSK           | TCP 9092, 9094, 9096 from VPC CIDR | All   |

## 4. IAM & IRSA

### Node Group Role

Attached policies:
- `AmazonEKSWorkerNodePolicy`
- `AmazonEKS_CNI_Policy`
- `AmazonEC2ContainerRegistryReadOnly`
- `AmazonSSMManagedInstanceCore`

### IRSA Roles

| Role Name                      | Service Account             | Permissions                    |
|--------------------------------|-----------------------------|--------------------------------|
| `aion-<env>-vpc-cni`         | `kube-system:aws-node`     | VPC CNI management             |
| `aion-<env>-ebs-csi`         | `kube-system:ebs-csi-*`    | EBS volume management          |
| `aion-<env>-msk-access`      | `aion:aion-kafka`          | Kafka cluster connect/read/write |
| `aion-<env>-s3-access`       | `aion:aion-s3`             | S3 get/put/list/delete         |
| `aion-<env>-rds-access`      | `aion:aion-rds`            | (Reserved for app-level DB ops)|
| `aion-<env>-generic-access`  | `aion:aion-generic`        | (Extensible for custom policies)|

All IRSA roles use the OIDC provider from the EKS cluster. Service accounts are created in the `aion` namespace with role ARN annotations.

## 5. Kubernetes Resources

| Resource             | Name       | Namespace |
|----------------------|------------|-----------|
| Namespace            | `aion`     | —         |
| ServiceAccount       | `aion-kafka` | `aion`  |
| ServiceAccount       | `aion-s3`    | `aion`  |
| ServiceAccount       | `aion-rds`   | `aion`  |
| ServiceAccount       | `aion-generic`| `aion` |

Labels on namespace: `environment = <env>`

## 6. Terraform Configuration

### File Structure

```
terraform/
├── main.tf         # All resource definitions
├── variables.tf    # Input variables with defaults
└── outputs.tf      # Cluster endpoints, connection strings, ARNs
```

### Providers

| Provider    | Version  | Purpose            |
|-------------|----------|--------------------|
| `aws`       | ~> 5.0   | All AWS resources  |
| `kubernetes`| ~> 2.25  | K8s namespace/SAs  |
| `tls`       | ~> 4.0   | Certificate ops    |

### Backend

- S3 bucket: `aion-terraform-state`
- State key: `eks/terraform.tfstate`
- DynamoDB lock: `terraform-lock`
- Encryption: enabled

### Variables (25 total)

**General:**
- `aws_region` = `eu-west-1`
- `environment` = `development` | `staging` | `production`
- `namespace` = `aion`

**VPC:**
- `vpc_cidr` = `10.0.0.0/16`
- `private_subnet_cidrs` = `["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]`
- `public_subnet_cidrs` = `["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]`

**EKS:**
- `eks_cluster_version` = `1.29`
- `system_instance_types` = `["m6i.xlarge", "m6i.2xlarge"]`
- `system_desired_size` = `2`
- `system_min_size` = `2`
- `system_max_size` = `4`
- `worker_instance_types` = `["m6i.xlarge", "m6i.2xlarge", "m5.xlarge", "m5.2xlarge", "c6i.xlarge", "c6i.2xlarge"]`
- `worker_desired_size` = `3`
- `worker_min_size` = `2`
- `worker_max_size` = `10`

**IRSA:**
- `mks_service_account_name` = `aion-kafka`
- `s3_service_account_name` = `aion-s3`
- `rds_service_account_name` = `aion-rds`
- `generic_service_account_name` = `aion-generic`

**RDS:**
- `rds_engine_version` = `15.4`
- `rds_instance_class` = `db.r6g.large`
- `database_name` = `aion`
- `database_master_username` = `aion_admin` (sensitive)
- `database_master_password` = (sensitive, required)

**MSK:**
- `msk_kafka_version` = `3.5.1`
- `msk_broker_count` = `3`
- `msk_instance_type` = `kafka.m5.large`
- `msk_volume_size` = `100`

### Outputs

| Output                            | Description                          |
|-----------------------------------|--------------------------------------|
| `vpc_id`                          | VPC ID                               |
| `private_subnets`                 | Private subnet IDs                   |
| `public_subnets`                  | Public subnet IDs                    |
| `nat_gateway_ips`                 | NAT Gateway public IPs               |
| `cluster_name`                    | EKS cluster name                     |
| `cluster_endpoint`                | EKS API server URL                   |
| `cluster_arn`                     | EKS cluster ARN                      |
| `cluster_oidc_provider_arn`       | OIDC provider ARN for IRSA           |
| `kubeconfig_command`              | `aws eks update-kubeconfig ...`      |
| `kubeconfig`                      | Full kubeconfig YAML (sensitive)     |
| `rds_cluster_endpoint`            | PostgreSQL writer endpoint           |
| `rds_cluster_reader_endpoint`     | PostgreSQL reader endpoint           |
| `rds_cluster_port`                | PostgreSQL port (5432)               |
| `database_name`                   | Database name                        |
| `database_connection_string`      | postgresql:// connection (sensitive) |
| `database_connection_string_ssl`  | postgresql:// with sslmode=require   |
| `msk_bootstrap_brokers`          | Kafka plaintext brokers              |
| `msk_bootstrap_brokers_tls`      | Kafka TLS brokers                    |
| `msk_zookeeper_connect_string`   | ZooKeeper connect string             |
| `msk_irsa_role_arn`              | MSK IRSA role ARN                    |
| `s3_irsa_role_arn`               | S3 IRSA role ARN                     |
| `rds_irsa_role_arn`              | RDS IRSA role ARN                    |
| `generic_irsa_role_arn`          | Generic IRSA role ARN                |
| `kafka_service_account`          | kafka SA namespace/name              |
| `s3_service_account`             | s3 SA namespace/name                 |
| `rds_service_account`            | rds SA namespace/name                |
| `generic_service_account`        | generic SA namespace/name            |
| `next_steps`                     | Post-deployment instructions         |

## 7. Deployment Workflow

```bash
# 1. Initialize
cd terraform
terraform init

# 2. Plan (review changes)
terraform plan -var="database_master_password=<SECRET>"

# 3. Apply
terraform apply -var="database_master_password=<SECRET>"

# 4. Configure kubectl
aws eks update-kubeconfig --name aion-development-eks --region eu-west-1

# 5. Verify
kubectl get nodes
kubectl get pods -n aion
kubectl get sa -n aion -o yaml
```

## 8. Scaling Guide

### Add More Worker Nodes
```hcl
# In terraform.tfvars or -var flag
worker_desired_size = 5
worker_max_size     = 15
```
Then `terraform apply`.

### Add a New IRSA Role
1. Add a new `module "<name>_irsa"` block in `main.tf` using the `iam-role-for-service-accounts-eks` module
2. Add a `kubernetes_service_account` with the IRSA annotation
3. Add any inline IAM policies for the specific permissions
4. Output the role ARN

### Upgrade Kubernetes Version
1. Update `eks_cluster_version` variable
2. Run `terraform plan` — EKS will perform a managed upgrade
3. Node groups will be updated automatically

### Upgrade Kafka Version
1. Update `msk_kafka_version` variable
2. Update `aws_msk_configuration.kafka` with the new version
3. Run `terraform apply` — MSK performs a rolling upgrade

## 9. Security Rules

| Rule                                                    | Enforcement         |
|---------------------------------------------------------|---------------------|
| No credentials in source code                           | `.gitignore` + env vars |
| `database_master_password` is sensitive                 | Terraform sensitive |
| RDS encryption at rest                                  | AWS-managed key     |
| MSK encryption in transit                               | TLS enforced        |
| MSK encryption at rest                                  | Custom KMS key      |
| Spot instances only on workers                          | Taints + labels     |
| Pod-to-AWS access via IRSA only                         | No long-lived creds |
| Network access restricted by SG CIDR                    | VPC-only reach      |
| Deletion protection on prod RDS                         | `deletion_protection = true` |
| 14-day backups on prod                                  | `backup_retention_period = 14` |

## 10. Environment Differences

| Setting                | Development          | Staging              | Production           |
|------------------------|----------------------|----------------------|----------------------|
| NAT Gateways           | 1                    | 1                    | 3 (one per AZ)       |
| RDS Instances          | 1                    | 1                    | 2 (Multi-AZ)         |
| RDS Backup Retention   | 7 days               | 7 days               | 14 days              |
| Deletion Protection    | No                   | No                   | Yes                  |
| Skip Final Snapshot    | Yes                  | Yes                  | No                   |
| System Nodes           | 2-4                  | 2-4                  | 2-4                  |
| Worker Nodes           | 2-10                 | 2-10                 | 2-10                 |
