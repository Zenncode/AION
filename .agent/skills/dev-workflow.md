# Developer Workflow

## Adding a New Feature

1. Create feature branch from `develop`
2. Implement changes in the appropriate subsystem directory
3. Add tests (unit + integration)
4. Update `.agent/context.md` if adding new files
5. Submit PR → Jenkins CI runs lint + build
6. Merge to `develop` → ArgoCD auto-syncs to dev environment
7. Test in dev namespace
8. Merge to `main` → ArgoCD syncs to staging, then production

## Adding a New Gold Table

1. Write DDL in `storage/iceberg/sql/003_<table>.sql`
2. Add PyIceberg ingestion in `storage/pyiceberg/ingest_gold_tables.py`
3. Add Feast feature view in `mlops/feast/feature_repo/features.py`
4. Add GraphQL resolver in the API gateway
5. Add AG-Grid column definitions in `src/components/grid/DataTable.tsx`
6. Run `feast apply` to register features

## Adding a New K8s Component

1. Create YAML in `<subsystem>/k8s/<component>.yaml`
2. Remove hardcoded namespace (kustomize manages it)
3. Add to `cicd/kustomize/base/kustomization.yaml` resources
4. Add replica/memory overrides in each env overlay
5. Add IRSA service account if AWS access needed
6. Add Prometheus metrics annotations if applicable

## Running Tests Locally

```bash
# Frontend
npm run lint && npm run type-check

# Copilot
cd copilot && python -m pytest app/ -v

# Flink (compile check)
cd ingestion/flink && mvn compile -q

# Terraform validate
cd terraform && terraform validate
```

## Local Development Stack

```bash
# Start local infra
cd ingestion/docker && docker compose up -d

# Start frontend dev server
cd . && npm run dev

# Start copilot API
cd copilot && uvicorn app.main:app --reload

# Access:
# Frontend:  http://localhost:3000
# Copilot:   http://localhost:8000/docs
# Flink UI:  http://localhost:8081
# Kafka UI:  http://localhost:9090
# Spark UI:  http://localhost:8082
```

## Code Review Checklist

- [ ] No hardcoded credentials or secrets
- [ ] No hardcoded namespaces in k8s manifests
- [ ] Resource requests and limits set on containers
- [ ] Probes configured for all deployments
- [ ] Sensitive Terraform outputs marked as sensitive
- [ ] Guardrails updated if adding new API endpoints
- [ ] Feature store updated if adding new ML features
- [ ] Prometheus metrics added for new services
