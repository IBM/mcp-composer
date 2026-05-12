# MCP Composer Product Roadmap (2026)

This roadmap prioritizes the next high-impact capabilities for MCP Composer, with a focus on catalog operations, governance, and production readiness.

## Product Direction

MCP Composer should evolve from "catalog CRUD + orchestration" to a platform that supports:

- safe publishing and lifecycle management
- tenant-level self-service with policy enforcement
- workflow marketplace distribution and reuse
- workflow-to-job execution by agents
- fast discovery at scale
- observability-driven operations
- repeatable promotion across environments

## Priority Use Cases

1. **Catalog Promotion Across Environments**
   - Teams publish in dev, promote to stage/prod with approvals and traceability.

2. **Tenant Self-Service Catalog Management**
   - Tenant admins publish and manage tenant-scoped resources safely.

3. **Large-Scale Resource Discovery**
   - Users quickly find the right skill/agent/workflow with hybrid search and metadata filters.

4. **Controlled Rollout and Rollback**
   - Operators can canary, monitor, and rollback problematic versions rapidly.

5. **Workflow Marketplace**
   - Teams can publish, discover, rate, version, and reuse approved workflows.

6. **Workflow as Agent-Executable Jobs**
   - A workflow can be returned/scheduled as a job and executed by an assigned agent.

7. **Governed and Auditable Changes**
   - Every mutation is attributable, policy-checked, and recoverable.

---

## 2026 Release Plan

### Release v0.3 - Catalog Safety and Governance
**Target Window:** 2026 Q2  
**Theme:** Prevent invalid releases and improve operational confidence.

#### Goals
- block invalid resources before activation
- reduce accidental data loss
- make catalog updates fully auditable

#### Included Features
1. **Publish Validation and Linting**
   - schema and metadata validation for skills/agents/workflows
   - semantic version validation and status-transition rules
   - reference URL/file safety checks

2. **Dry-Run Publish**
   - preview create/update effects before writing
   - return warnings and policy violations without side effects

3. **Audit Trail**
   - track actor, timestamp, tenant, action, and before/after state
   - support audit queries by resource and tenant

4. **Soft Delete + Restore Window**
   - replace immediate hard deletes with retention-based recovery
   - allow restore for recent deletions

#### Success Metrics
- 80% reduction in invalid publish attempts reaching active status
- 100% catalog write actions produce audit entries
- < 5 minutes mean time to recover accidentally deleted resource versions

---

### Release v0.4 - Promotion and Progressive Delivery
**Target Window:** 2026 Q3  
**Theme:** Make multi-environment and staged rollout workflows first-class.

#### Goals
- standardize dev -> stage -> prod movement
- lower blast radius during version rollout
- improve deployment confidence for operators
- introduce workflow marketplace foundations

#### Included Features
1. **Environment Promotion Workflow**
   - promote resource versions between environments using explicit MCP tools
   - enforce approval hooks and policy gates before promotion

2. **Version Rollout Controls**
   - support `draft`, `active`, `canary`, `deprecated`, and `deleted` states
   - route a configurable percentage of traffic to canary versions

3. **One-Click Rollback**
   - rollback to last known good active version
   - persist rollback reason for post-incident review

4. **Promotion Eventing**
   - emit events for publish/promote/rollback actions for external automation

5. **Workflow Marketplace (Foundation)**
   - marketplace tools for publish/list/get/deprecate workflow packages
   - workflow metadata contract (owner, tags, category, rating, compatibility)
   - approval pipeline for "verified" marketplace workflows

#### Success Metrics
- < 10 minutes average promotion time (excluding manual approval wait)
- < 2 minutes rollback execution time
- 50% reduction in production incidents tied to catalog version changes

---

### Release v0.5 - Discovery and Dependency Intelligence
**Target Window:** 2026 Q4  
**Theme:** Improve discoverability, change impact awareness, and scale operations.

#### Goals
- help users find the right resources faster
- expose dependency risk before breaking changes
- improve platform-level insight and reliability
- execute workflows as jobs through agent runtimes

#### Included Features
1. **Hybrid Catalog Search**
   - combine keyword, semantic embedding, and structured filters
   - support tenant/product/license/tag/status filters

2. **Dependency Graph**
   - map relationships across skills, agents, workflows, and prompts
   - expose consumers of a given resource version

3. **Impact Analysis Tooling**
   - preview downstream impact of deprecating/deleting a version
   - block high-risk operations without explicit override

4. **Operational Telemetry and SLOs**
   - metrics for publish success rate, search latency, loader freshness, and error budgets
   - dashboard-ready outputs for monitoring tools

5. **Workflow Job Runtime for Agents**
   - `start_workflow_job`, `get_workflow_job`, `cancel_workflow_job`, and `list_workflow_jobs` MCP tools
   - asynchronous execution model with queue, retries, timeout, and idempotency keys
   - agent assignment policy (capability/tag/tenant-aware routing)
   - job state model: `queued`, `running`, `succeeded`, `failed`, `cancelled`

#### Success Metrics
- 40% faster median time-to-resource discovery
- 0 unintentional dependency breakages from unmanaged deprecations
- 99.9% success rate for catalog mutation operations
- 95% of workflow jobs start within target queue latency SLO
- 99% workflow job state transitions are traceable end-to-end

---

## Cross-Release Workstreams

| Workstream | Scope | Primary Owner | Status |
|------------|-------|---------------|--------|
| Catalog Governance | validation, policy, audit, soft-delete | Core Platform Team | Planned |
| Progressive Delivery | promotion, canary, rollback, events | Runtime Team | Planned |
| Workflow Marketplace | workflow package publishing, verification, discovery, reuse | Catalog Team | Planned |
| Agent Job Runtime | workflow job MCP tools, queueing, retries, agent routing | Runtime Team | Planned |
| Discovery Platform | hybrid search and filter tools/resources | Catalog Team | Planned |
| Dependency Intelligence | graph model and impact checks | Architecture Team | Planned |
| Observability | SLOs, telemetry, operational dashboards | Reliability Team | Planned |

## Reference Architecture (Marketplace + Agent Jobs)

This section defines a minimal target architecture so implementation can begin without additional design documents.

### Core Components

1. **Workflow Marketplace MCP Server**
   - manages workflow package publish/list/get/version/deprecate operations via tools
   - stores workflow metadata, compatibility, and verification status
   - exposes discovery through MCP tools/resources

2. **Workflow Registry and Artifact Store**
   - persists workflow definitions and immutable package versions
   - stores signed manifests and checksum metadata for integrity
   - supports tenant visibility and policy tags

3. **Job Orchestrator**
   - receives workflow execution tool calls and creates workflow jobs
   - validates workflow version, tenant policy, and execution constraints
   - drives job state transitions from queue to completion

4. **Execution Queue**
   - buffers asynchronous workflow jobs for agent execution
   - supports retry policy, dead-letter handling, timeout, and idempotency keys

5. **Agent Runner**
   - polls/receives assigned jobs, executes workflow steps, and reports progress
   - enforces capability and tenant boundaries during tool invocation
   - emits execution logs and final result payloads

6. **Observability and Audit Pipeline**
   - collects job events, state transitions, and execution metrics
   - exposes trace correlation from tool invocation to agent completion

### End-to-End Flow

1. Team publishes workflow package to marketplace.
2. Workflow passes validation and optional verification review.
3. User/system invokes a workflow execution MCP tool for `name@version`.
4. Job orchestrator creates `workflow_job_id` and enqueues the job.
5. Eligible agent runner claims job based on policy and capabilities.
6. Agent executes steps and updates job status/progress events.
7. Job completes (`succeeded`/`failed`/`cancelled`) with auditable result.

### Minimal MCP Tool Contract (First Iteration)

- Marketplace
  - `publish_workflow_package`
  - `list_workflow_packages`
  - `get_workflow_package`
  - `deprecate_workflow_package`
- Job Runtime
  - `start_workflow_job`
  - `get_workflow_job`
  - `list_workflow_jobs`
  - `cancel_workflow_job`
  - `retry_workflow_job`

### Job Data Model (Initial)

- `job_id`
- `tenant_id`
- `workflow_name`
- `workflow_version`
- `status` (`queued`, `running`, `succeeded`, `failed`, `cancelled`)
- `priority`
- `requested_by`
- `assigned_agent_id`
- `idempotency_key`
- `created_at`, `started_at`, `finished_at`
- `result_ref` (pointer to output payload/artifact)
- `error_code`, `error_message`

### Non-Functional Targets

- P95 queue wait time under defined SLO for standard priority jobs
- deterministic idempotent behavior for duplicate tool invocations
- full auditability of publish, assignment, execution, and cancellation events
- tenant isolation across marketplace visibility and runtime execution

## Implementation Notes

- Keep backward compatibility for existing catalog tools where possible.
- Introduce new capabilities as additive MCP tools/resources first, then phase-in stricter defaults.
- Ship docs and examples with every release milestone to reduce adoption friction.