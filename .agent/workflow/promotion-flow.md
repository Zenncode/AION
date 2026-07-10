# Environment Promotion Flow

## Code Path: Dev → Staging → Production

```
Developer pushes to feature/* branch
        │
        ▼
   Jenkins CI (lint, build, test)
        │
        ▼
   Merge to develop
        │
        ▼
   ArgoCD syncs → aion-dev namespace
        │
        ▼
   Manual QA in dev
        │
        ▼
   Merge develop → main
        │
        ▼
   Jenkins builds images → ECR (tag: main-<hash>)
        │
        ▼
   Commit updated kustomization.yaml to gitops repo
        │
        ▼
   ArgoCD syncs → aion-staging namespace (auto)
        │
        ▼
   Integration tests in staging
        │
        ▼
   ArgoCD syncs → aion-production namespace (auto)
        │
        ▼
   Post-deploy verification
```

## Rollback Procedure

```bash
# Via ArgoCD
argocd app rollback aion-production <previous-revision>

# Via Kustomize (revert git commit)
git revert <commit-hash>
git push origin main
# ArgoCD auto-syncs the reverted state

# Emergency: force specific image
argocd app set aion-production \
  -p "images[0].newTag=<known-good-tag>"
```

## Image Tag Convention

```
<component>:<build-number>-<git-short-hash>

Examples:
  aion/frontend:42-a1b2c3d
  aion/copilot:42-a1b2c3d
  aion/flink:42-a1b2c3d
```

## Pre-deploy Checklist

- [ ] All CI checks passing
- [ ] Staging environment validated
- [ ] Database migrations tested (if applicable)
- [ ] Feature flags configured
- [ ] Monitoring dashboards reviewed
- [ ] On-call engineer notified
- [ ] Rollback plan documented
