# Component Design Standards

## Frontend Component Structure

Every React component follows:

```
ComponentName/
├── ComponentName.tsx       # Main component
├── ComponentName.test.tsx  # Unit tests
├── index.ts                # Re-export
└── types.ts                # Local type definitions (if complex)
```

### Naming Conventions
- Components: PascalCase (`Dashboard`, `KPICard`, `Copilot`)
- Hooks: camelCase with `use` prefix (`useKpiData`, `useCopilotChat`)
- Utilities: camelCase (`formatCurrency`, `inferChartType`)
- Types: PascalCase with descriptive names (`RevenueMetrics`, `ChatMessage`)
- CSS classes: Tailwind utility classes, no custom CSS unless animated

### State Management
- Local state: `useState` for UI-only state
- Server state: Apollo Client cache (no Redux/Zustand)
- URL state: `react-router-dom` search params for filters/sorting
- Auth state: Keycloak context via `@react-keycloak/web`

---

## Backend Component Structure (Copilot)

```
copilot/app/
├── main.py              # FastAPI app, routes, lifespan
├── core/config.py       # All settings in one dataclass
├── rag/
│   ├── pipeline.py      # Orchestrates retrieval → SQL → summary
│   ├── vector_store.py  # Qdrant wrapper
│   ├── embeddings.py    # OpenAI embeddings + fallback
│   ├── trino_client.py  # SQL execution
│   └── prompts.py       # All prompt templates
├── guardrails/safety.py # Input validation + SQL output validation
├── llm/client.py        # Unified Claude/GPT-4 interface
└── ingestion/document_loader.py  # PDF/schema chunking
```

### Error Handling
- API errors return structured JSON with error codes
- Guardrail blocks return safe message, never leak internal state
- SQL execution failures return error message, never crash the pipeline
- LLM failures fall back to the other provider if available

---

## Terraform Module Standards

- One `main.tf` per logical grouping (VPC, EKS, RDS, MSK)
- All variables defined in `variables.tf` with descriptions
- All outputs in `outputs.tf` with descriptions
- Sensitive values marked `sensitive = true`
- Tags always include: Project, Environment, ManagedBy
- Naming: `${local.name_prefix}-<component>`

---

## Kubernetes Manifest Standards

- Labels: `app`, `app.kubernetes.io/name`, `app.kubernetes.io/component`
- No hardcoded namespaces — kustomize overlays manage them
- Resource requests + limits on every container
- Liveness + readiness probes on every deployment
- PDBs on stateful or critical workloads
- IRSA for all AWS API access (no long-lived credentials)
