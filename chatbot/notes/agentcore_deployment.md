> This is a proposed infrastructure migration, not a description of an implemented change. Terminology and reference paths have been updated; no AgentCore migration was performed.

# Reimagining the Binary Necklaces Chatbot on Amazon Bedrock AgentCore

This document describes how the current Binary Necklaces chatbot deployment would be
re-architected for a production environment — regular traffic, a team of
engineers, real users — using **Amazon Bedrock AgentCore** instead of a
single hand-managed EC2 instance.

It is written against the system as it actually exists today (see
`mcp/main.py`, `mcp/binary_necklaces.py`, `mcp/roles.py`, `ami/`, and the deploy
scripts), not a generic example.

---

## 1. Executive summary

The current design is a clever, working prototype, but it concentrates the
entire backend onto one EC2 instance that the owner administers by hand:
Nginx, Docker, Let's Encrypt, fail2ban, SSH-based deploys, a public IP behind
Route 53, and an unauthenticated `/mcp` endpoint. It is a single point of
failure with no horizontal scaling, no per-user isolation, no authentication,
and observability limited to four hand-emitted CloudWatch token counters.

AgentCore lets us delete almost all of that undifferentiated infrastructure
and keep only the parts that carry actual product value: the React frontend,
the Bedrock model choice, prompt caching, the multi-agent orchestration logic,
and the Bitcalc tool. The orchestrator moves into **AgentCore Runtime**
(serverless, session-isolated microVMs), the Binary Necklaces tool moves behind
**AgentCore Gateway** (a managed MCP endpoint), access is gated by
**AgentCore Identity** (Cognito/OIDC), conversation state and personalization
come from **AgentCore Memory**, and tracing/metrics come for free from
**AgentCore Observability**.

The frontend (S3 + CloudFront) barely changes. The EC2 instance, the custom
AMI, the Nginx config, the SSL renewal timers, the fail2ban jail, the
ECR-pull-on-boot user-data, and the SSH deploy loop all go away.

---

## 2. The current architecture (what we are replacing)

### 2.1 Request flow today

1. Browser loads the React chat UI from `malcolmblack.org` (S3 static site via
   CloudFront).
2. The UI POSTs the user's question to `/mcp`, a CloudFront behavior whose
   custom origin is `mcp.malcolmblack.org`.
3. Route 53 resolves `mcp.malcolmblack.org` to the **public IP of a single EC2
   instance** (`i-0c8ccad1a84cd54b8`, `t4g.small`, `us-west-2b`).
4. Nginx on the instance terminates TLS (Let's Encrypt) and reverse-proxies to
   a Docker container running `uvicorn` on `:8000`.
5. The FastAPI app (`main.py`) is itself an **MCP client + orchestrator**. On
   startup it spawns `binary_necklaces.py` as a local stdio subprocess (the MCP tool
   server) and caches the research paper + tool list.
6. For each query it runs the multi-agent orchestration against the Bedrock
   Converse API and streams SSE status events back to the browser.

### 2.2 The orchestration (the actual product)

This is the valuable part and it is worth preserving exactly:

- Two **parallel pipelines**, each `First Responder → Skeptic → Arbiter`.
- A **Judge** then picks the better of the two Arbiter answers.
- That is roughly **13 Bedrock calls per user question** (3 roles × 2
  pipelines = 6, plus the Judge, plus tool-use follow-up turns).
- The ~17k-token research paper is pinned in the system prompt with a
  `cachePoint`, so Bedrock prompt caching avoids re-billing it on every call.
- The only tool is `get_properties`, which calls the external Bitcalc API at
  `malcolmblack.org/api/bitloops/calc`. The paper itself is an MCP *resource*
  fetched from `malcolmblack.org/binary-necklaces/binary-necklaces.yml`.
- Token usage (`input`, `output`, `cacheRead`, `cacheWrite`) is pushed to a
  custom CloudWatch namespace `BitloopsChatbot`.

### 2.3 Why this does not survive contact with production

| Concern | Current state | Consequence |
|---|---|---|
| Availability | One EC2 instance, one AZ | Instance or AZ failure = full outage |
| Scaling | Fixed `t4g.small`, `--network host` | Concurrent users contend for one box; no autoscale |
| Isolation | All requests share one process | No per-user/session boundary; one bad request can affect all |
| AuthN/AuthZ | `/mcp` is open to the world | Anyone can drive your Bedrock spend; no user identity |
| TLS | Manual Let's Encrypt + cron renewal | Renewal failure = outage; toil |
| Deploys | Zip → S3 → SSH → `docker build` on the box | Manual, no rollback, build runs in prod, drift-prone |
| Patching | Custom AMI, fail2ban, SSH on 22 | You own OS patching and intrusion hardening |
| State | Stateless; every query independent | No conversation continuity, no personalization |
| Observability | 4 hand-emitted token metrics | No traces, no per-role latency, no error breakdown |
| Secrets/identity for tools | Implicit (open API) | No managed inbound/outbound auth story |

---

## 3. AgentCore building blocks (and how each maps here)

AgentCore is a suite of modular, independently-usable services. The ones
relevant to this workload:

- **AgentCore Runtime** — serverless, secure hosting for agents / tools / MCP
  servers. Each user **session runs in its own microVM** with isolated CPU,
  memory, and filesystem; the microVM is torn down and memory sanitized when
  the session ends. Sessions can persist up to **8 hours**, pricing is
  **consumption-based** (you are billed for active processing, not while
  blocked waiting on an LLM or tool), and it is **framework-agnostic**
  (Strands, LangGraph, CrewAI, or plain Python) and model-agnostic.
- **AgentCore Gateway** — a managed, MCP-native tool server. It turns Lambda
  functions, OpenAPI specs, or existing MCP servers into agent-discoverable
  tools behind one endpoint, with built-in inbound authorization and outbound
  credential injection.
- **AgentCore Identity** — identity and credential management for agents:
  inbound JWT authorizers backed by Cognito / Microsoft Entra / Okta, and
  outbound credential providers (OAuth, API keys) for third-party calls.
- **AgentCore Memory** — managed short-term memory (conversation history) and
  long-term memory (facts, preferences), **namespaced per user** so context
  stays private.
- **AgentCore Observability** — OpenTelemetry-compatible traces, spans, and
  metrics surfaced in the CloudWatch GenAI Observability console: session
  count, latency, duration, token usage, error rates, per-step traces.

---

## 4. Target architecture

### 4.1 New request flow

```
Browser (React, on S3 + CloudFront)
   │  1. user signs in (Cognito Hosted UI / OIDC) → JWT
   │  2. POST question + JWT  ──► CloudFront  /api/chat
   ▼
API layer  (CloudFront → API Gateway → Lambda, or AppSync)
   │  • validates the Cognito JWT
   │  • owns the user → session_id mapping (AgentCore does NOT enforce this)
   │  • calls InvokeAgentRuntime with the session id + (passes the JWT through)
   ▼
AgentCore Runtime  (the orchestrator agent, one microVM per session)
   │  • runs First Responder → Skeptic → Arbiter ×2  +  Judge
   │  • calls Bedrock Converse (Claude Sonnet 4.5) with the cached paper
   │  • reads/writes AgentCore Memory (history + user preferences)
   │  • discovers + calls tools through the Gateway MCP endpoint
   ▼
AgentCore Gateway  (managed MCP endpoint, inbound auth via Identity)
   ▼
get_properties tool  (Lambda target)  ──►  Bitcalc API
```

Two important design notes:

- **The browser never calls AgentCore Runtime directly.** Runtime is invoked
  through the `InvokeAgentRuntime` API (SigV4/IAM or OAuth), not from public
  untrusted clients. A thin API layer (API Gateway + Lambda, or AppSync) sits
  in front to validate the user's token, enforce the user↔session mapping and
  per-user session limits, and stream the response back. This replaces the
  hand-rolled `/mcp` SSE endpoint on EC2.
- **Streaming status updates** (`first_responder`, `skeptic`, … `done`) that
  `main.py` currently emits over SSE are preserved by streaming from the
  Runtime invocation back through the API layer to the browser.

### 4.2 Component-by-component mapping

| Today | Becomes | Notes |
|---|---|---|
| React UI on S3 + CloudFront (`malcolmblack.org`) | **Unchanged** | Add a Cognito Hosted UI / OIDC sign-in; point the chat call at `/api/*` instead of `/mcp`. |
| CloudFront `/mcp` → custom origin `mcp.malcolmblack.org` | CloudFront `/api/*` → **API Gateway + Lambda** | No more custom origin to an EC2 box. |
| Route 53 A record → EC2 public IP | **Deleted** | No public IP, no DNS-to-instance mapping. |
| EC2 instance + custom AMI + Nginx + Let's Encrypt + fail2ban + user-data | **AgentCore Runtime** | Serverless; AWS owns the host, TLS, patching, isolation. |
| `main.py` orchestrator (MCP client + Bedrock loop) | **Agent deployed to AgentCore Runtime** | Same orchestration logic; see §5.1. |
| `binary_necklaces.py` MCP tool server (`get_properties`, paper resource) | **AgentCore Gateway target** (Lambda or MCP-server target) | See §5.2. |
| No auth on `/mcp` | **AgentCore Identity** (inbound JWT via Cognito) | Gateway + Runtime both enforce it. |
| Stateless; no memory | **AgentCore Memory** | Multi-turn conversations + per-user personalization. |
| `send_tokens_to_cloudwatch()` custom metrics | **AgentCore Observability** | Tokens, latency, per-role spans, errors out of the box. |
| Zip → S3 → SSH → `docker build` on prod | **CI/CD: build image → ECR → `agentcore` deploy** | See §6. |
| Bedrock Converse + `cachePoint` prompt caching | **Unchanged** | The model call and caching strategy carry over verbatim. |
| Bitcalc API (`/api/bitloops/calc`) | **Unchanged** | Still an external HTTP dependency, now called from the Lambda tool. |

---

## 5. Code-level changes

There are two reasonable migration depths. Pick based on how much you want to
refactor.

### 5.1 The orchestrator → AgentCore Runtime

**Option A — minimal lift (lift-and-shift the container).**
The existing FastAPI app is already containerized. AgentCore Runtime hosts
arbitrary containers that implement its HTTP service contract (`POST
/invocations`, `GET /ping`). The smallest change is to adapt the current
`/mcp` handler to that contract, keep the orchestration code in `main.py`
exactly as is, and let Runtime provide isolation/scaling/TLS. You lose nothing
and delete all the EC2/Nginx/AMI machinery immediately.

**Option B — idiomatic (recommended over time).**
Re-express the orchestrator with a supported agent framework (e.g. **Strands
Agents**) wrapped in `BedrockAgentCoreApp`. The roles in `roles.py` map
naturally to a small graph of agent invocations; the parallel pipelines become
two concurrent sub-runs and the Judge a final reducer. Benefits: the framework
emits richer OTEL spans (each role becomes a visible span in the trace), tool
calls through the Gateway are handled by the framework's MCP client instead of
the hand-written `process_query` tool loop, and Memory integration is a hook
rather than custom code.

What stays identical in both options:

- `modelId='us.anthropic.claude-sonnet-4-5-20250929-v1:0'`,
  `inferenceConfig`, and the `system` array with `{'cachePoint': ...}` — the
  prompt-caching trick that keeps the 17k-token paper cheap is unchanged.
- The role prompts and query templates in `roles.py`.
- The two-pipeline + Judge accuracy strategy described in the README.

What changes:

- `connect_to_server()` no longer spawns `binary_necklaces.py` over stdio. Instead the
  agent points at the **Gateway MCP endpoint** and lists/calls tools there.
- `send_tokens_to_cloudwatch()` is deleted; token metrics come from
  Observability. (You can still emit custom business metrics if you want.)
- Conversation history is no longer rebuilt per request from scratch — it is
  loaded from Memory for the session.

### 5.2 The Binary Necklaces tool → AgentCore Gateway

`binary_necklaces.py` exposes one tool (`get_properties`) and one resource (the YAML
paper). Two ways to host it behind Gateway:

- **Lambda target (recommended).** Move `get_properties` into a Lambda function
  with the same input schema (`{"state": "<binary-word>"}`) and register it as a
  Gateway target. Gateway generates the MCP tool schema and exposes it on the
  unified endpoint. This is the most "serverless-native" option and removes the
  stdio subprocess entirely.
- **MCP-server target.** Keep `binary_necklaces.py` as a streamable-HTTP MCP server
  (FastMCP already supports this — `mcp.run(transport="streamable-http")` on
  `0.0.0.0:8000/mcp`) and attach it to Gateway as an MCP-server target. Lower
  refactor, but you still host that server somewhere (it can itself run on
  AgentCore Runtime).

The **research paper** is better modeled not as a tool at all:

- Short term: keep fetching the YAML over HTTP inside the agent and pin it in
  the cached system prompt, exactly as today.
- Longer term: if the paper grows, move to selective retrieval (the README
  already anticipates this) using a knowledge base / retrieval tool behind the
  Gateway, so roles request only the concepts they need instead of the whole
  document.

Outbound auth: if the Bitcalc API ever requires credentials, those live in an
**AgentCore Identity credential provider** and are injected by Gateway, rather
than being baked into the container.

---

## 6. CI/CD and deployment

Replace the `zip → S3 → SSH → docker build on the prod box` loop (which builds
in production and has no rollback) with a standard pipeline:

1. Engineer merges to `main`.
2. CodePipeline / GitHub Actions builds the agent container (ARM64) and pushes
   to the existing **ECR** repo `mcp`.
3. The pipeline deploys a new Runtime version via the **`agentcore` CLI** (or
   `CreateAgentRuntimeVersion` / CloudFormation / CDK / Terraform). Gateway
   targets and Memory/Identity config are defined as IaC.
4. Promote across environments (dev → staging → prod) with separate Runtime
   endpoints; roll back by pointing the endpoint at the previous version.

Benefits over today: builds happen off the serving path, every deploy is
versioned and reversible, infrastructure is declarative, and no human needs
SSH access to anything.

---

## 7. Security improvements

- **Authentication.** The open `/mcp` endpoint is replaced by Cognito-issued
  JWTs validated at the API layer and again by AgentCore Identity at the
  Gateway/Runtime boundary. Only signed-in users can spend your Bedrock budget.
- **No public attack surface on a host you own.** No public EC2 IP, no SSH on
  port 22, no Nginx to patch, no fail2ban to tune. AWS owns the host.
- **Session isolation.** Each user session runs in a dedicated microVM with
  isolated compute/memory/filesystem; memory is sanitized at session end,
  preventing cross-user contamination — impossible to guarantee in today's
  single shared process.
- **Managed TLS.** No more Let's Encrypt renewal timers that can silently fail.
- **Outbound credential management.** Third-party tool credentials are managed
  by Identity, not embedded in the image.
- **Encryption control.** Customer-managed KMS keys can encrypt session data.

> Note: AgentCore does not enforce the user→session mapping for you. The API
> layer must own that relationship (and per-user session caps) so one user
> cannot resume another user's session.

---

## 8. Scalability and availability

- **Horizontal scale by session.** Runtime provisions a microVM per session
  and scales to zero when idle, instead of contending on one `t4g.small`.
- **No single point of failure / no AZ pinning.** The managed service replaces
  the single-instance, single-AZ deployment.
- **Cost shape fits this workload.** Consumption-based pricing bills for active
  processing rather than idle time. That matters here because each query fans
  out to ~13 Bedrock calls and spends much of its wall-clock time *waiting* on
  the model — time you are not billed for at the Runtime layer (Bedrock token
  cost is separate and unchanged).
- **Long-running headroom.** Sessions up to 8 hours comfortably cover the
  multi-step, multi-agent deliberation even under load or with retries.

---

## 9. Observability upgrade

The current four custom metrics become a small subset of what Observability
provides automatically:

- Session count, latency, duration, token usage, and error rates in the
  CloudWatch GenAI Observability dashboards.
- **Per-step traces**: with the framework-based orchestrator, each role
  (First Responder, Skeptic, Arbiter ×2, Judge) and each tool call appears as a
  span, so you can see exactly where latency or errors come from in the
  pipeline — something the current design cannot show at all.
- OTEL-compatible export into any existing monitoring stack.
- You can still emit custom business metrics (e.g. answer-correctness sampling)
  on top.

---

## 10. What we deliberately keep

Not everything should change. The following are already good and carry over:

- The **React frontend on S3 + CloudFront** — static hosting is the right tool;
  only the backend call target and a sign-in step change.
- The **model choice and Bedrock Converse usage**, including the `cachePoint`
  prompt-caching strategy for the research paper.
- The **multi-agent orchestration design** and the role prompts — this is the
  product's differentiator and the measured accuracy gains (82% → 94%) depend
  on it.
- The **Bitcalc API** as the source of truth for binary necklace properties.
- **ECR** as the image registry and **us-west-2** as the region.

---

## 11. Trade-offs and when this is overkill

- **Cost at low traffic.** For a personal hobby project with sporadic traffic,
  one `t4g.small` is cheaper and simpler. AgentCore earns its keep when you
  have regular traffic, multiple users, a team, and uptime expectations — which
  is the premise of this exercise.
- **Refactor effort.** Option B (idiomatic Strands + Gateway + Memory) is more
  work than the lift-and-shift. A pragmatic path is to ship Option A first
  (delete the EC2/AMI/Nginx toil immediately) and adopt Gateway/Memory/Identity
  incrementally.
- **Service maturity.** AgentCore is comparatively new; some teams will want to
  pin SDK/CLI versions and validate quotas and regional availability before
  committing.
- **Fan-out cost is unchanged.** AgentCore does not reduce the ~13 Bedrock
  calls per question — that is inherent to the orchestration. Prompt caching
  remains the main lever, and Observability now makes the token spend per role
  visible so you can tune it.

---

## 12. Phased migration plan

1. **Stand up identity.** Create a Cognito user pool; add sign-in to the React
   app. (Frontend stays on S3/CloudFront.)
2. **Move the tool.** Reimplement `get_properties` as a Lambda and put it
   behind an AgentCore Gateway with the Cognito JWT authorizer. Verify with an
   MCP client.
3. **Move the orchestrator.** Containerize `main.py` to the Runtime service
   contract (Option A) and deploy to AgentCore Runtime; point it at the Gateway
   for tools instead of the stdio subprocess.
4. **Front it with an API.** Add API Gateway + Lambda that validates the JWT,
   manages session IDs, calls `InvokeAgentRuntime`, and streams results.
   Repoint CloudFront `/api/*` at it; retire `/mcp`, Route 53 record, and the
   EC2 instance.
5. **Turn on Observability** and replace the custom CloudWatch metrics.
6. **Add Memory** for multi-turn conversations and per-user personalization.
7. **Refactor to Strands (Option B)** for richer tracing and simpler tool/memory
   integration, once the rest is stable.
8. **Decommission** the AMI build, user-data, Nginx/SSL/fail2ban config, and
   SSH deploy scripts.

---

## References

- AgentCore Runtime — serverless hosting, microVM session isolation, 8h
  sessions, consumption pricing:
  https://aws.amazon.com/blogs/machine-learning/securely-launch-and-scale-your-agents-and-tools-on-amazon-bedrock-agentcore-runtime/
- Deploy MCP servers in AgentCore Runtime (MCP at `0.0.0.0:8000/mcp`, stateless
  vs stateful):
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
- AgentCore Gateway — turn Lambda/OpenAPI/MCP servers into managed tools:
  https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-gateway-transforming-enterprise-ai-agent-tool-development/
- AgentCore Identity — inbound JWT authorizers and outbound credentials:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html
- POC → production walkthrough (Memory, Gateway, Identity, Runtime together):
  https://aws.amazon.com/blogs/machine-learning/move-your-ai-agents-from-proof-of-concept-to-production-with-amazon-bedrock-agentcore/
- Enterprise best practices (session isolation, per-user memory, Gateway policy
  enforcement):
  https://aws.amazon.com/blogs/machine-learning/ai-agents-in-enterprises-best-practices-with-amazon-bedrock-agentcore/
- AgentCore Observability:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html
- Use isolated sessions for agents (session lifecycle, user↔session mapping):
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html

*Content from AWS documentation and blogs was rephrased for compliance with licensing restrictions.*
