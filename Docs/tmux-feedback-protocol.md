# tmux Cross-Agent Feedback Protocol

Purpose: BE, FE, and AI agents must be able to give actionable feedback to the orchestrator and to other domain agents through tmux without waiting for manual user intervention.

## Roles and panes

- Orchestrator pane: `orchest:1.1`
- Backend pane: `BE:1.1`
- Frontend pane: `FE:1.1`
- AI pane: `AI:1.1`

Each specialist owns its own repository and should normally not edit another repository directly. Cross-domain issues must be reported through this protocol.

## When an agent must send feedback

Send feedback when any of the following happens:

1. Contract mismatch
   - Endpoint path, method, request/response schema, SSE event shape, field name, enum, or error handling does not match another domain.
2. Integration blocker
   - A BE-AI, FE-BE, or FE-BE-AI flow cannot run because another domain is missing a behavior or returns incompatible data.
3. Safety/security concern
   - Hidden truth, private timeline, solution, secret, API keys, full prompt, or full player text could leak through payloads/logs/client fixtures.
4. Architecture/code-smell concern
   - Another domain contract encourages duplicated state, bypasses BE authority, forces FE to fake production truth, or lets AI become state authority.
5. Observability gap
   - A domain needs request_id/session_id/event_id/fallback/log fields from another domain to debug the E2E flow.
6. Commit/dogfood blocker
   - A milestone cannot be considered commit-ready until another domain fixes or confirms something.

## Feedback message format

Use this exact compact format so the receiving agent and orchestrator can triage quickly:

```text
[CROSS-FEEDBACK]
from: BE|FE|AI
to: ORCH|BE|FE|AI|ALL
severity: blocker|high|medium|low
category: contract|integration|safety|observability|architecture|dogfood|commit
summary: one-line actionable summary
context:
- repo/file/function/endpoint/event involved
- observed behavior or missing behavior
- expected behavior
request:
- exact change or confirmation needed
validation:
- command, API call, browser flow, or test that proves it is fixed
commit impact:
- commit-ready blocked: yes|no
- affected atomic milestone/message if known
```

## How to send feedback through tmux

Preferred: paste a short `/steer` message into the target pane and the orchestrator pane.

For example, from FE to BE and orchestrator:

```bash
tmux send-keys -t BE:1.1 "/steer [CROSS-FEEDBACK] from: FE to: BE severity: blocker category: contract summary: dialogue response missing visualState ..." C-m
tmux send-keys -t orchest:1.1 "/steer [CROSS-FEEDBACK] from: FE to: BE severity: blocker category: contract summary: dialogue response missing visualState ..." C-m
```

For multi-line feedback, write it to a temp file, load a tmux buffer, paste it into the target pane, then press Enter:

```bash
tmux load-buffer -b cross_feedback /tmp/cross_feedback.txt
tmux paste-buffer -b cross_feedback -t BE:1.1
tmux send-keys -t BE:1.1 C-m
tmux paste-buffer -b cross_feedback -t orchest:1.1
tmux send-keys -t orchest:1.1 C-m
```

Agents should keep messages short enough to avoid derailing active work. If the target pane is clearly `Working`, send only to `orchest:1.1` and mark `to:` with the intended domain; the orchestrator will route it when safe.

## Routing rules

- Always copy the orchestrator (`orchest:1.1`) on cross-domain feedback.
- If the receiving domain is idle or at prompt, send directly to that domain and copy orchestrator.
- If the receiving domain is actively working, send only to orchestrator to avoid interrupting. The orchestrator will queue or forward later.
- If feedback affects all domains or shared contracts, set `to: ALL` and copy orchestrator.
- If feedback is a blocker for commit/dogfood, use `severity: blocker` and `commit-ready blocked: yes`.

## Orchestrator duties

When the orchestrator receives `[CROSS-FEEDBACK]`:

1. Capture the relevant panes before acting.
2. Record the feedback in `Docs/orchestration-status.md`.
3. Classify the receiving pane as idle/working/blocked/done.
4. Forward to the responsible agent only when it is safe to interrupt, or queue it in the status log.
5. Ask the responsible agent for changed files, validation result, contract delta, and commit-ready impact.
6. Verify the fix centrally through API/browser/SSE/integration dogfood before accepting completion.

## Acceptance criteria

This protocol is active only when:

- BE/FE/AI `AGENTS.md` reference this document.
- Each agent's completion report includes cross-feedback sent/received or explicitly says `cross-feedback: none`.
- The orchestrator log records blocker feedback and routing decisions.
- Commit-ready reports include whether unresolved cross-feedback blocks the milestone.
