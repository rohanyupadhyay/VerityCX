---
tracker:
  kind: github
  provider:
    repo: rohanyupadhyay/VerityCX
    token: $GITHUB_TOKEN
    workflow_control:
      enabled: true
      authorized_associations:
        - OWNER
        - MEMBER
        - COLLABORATOR
  required_labels:
    - symphony
  active_states:
    - open
  terminal_states:
    - closed
polling:
  interval_ms: 30000
workspace:
  root: /home/rohan/code/symphony-workspaces/VerityCX
hooks:
  after_create: |
    git clone --depth 1 https://github.com/rohanyupadhyay/VerityCX.git .
    uv sync --locked
  timeout_ms: 300000
agent:
  max_concurrent_agents: 1
  max_turns: 20
codex:
  command: codex app-server
  approval_policy: never
  # Symphony agents need to create issue branches and commits. workspace-write
  # deliberately protects .git, so full access is scoped to isolated issue workspaces.
  thread_sandbox: danger-full-access
  turn_sandbox_policy:
    type: dangerFullAccess
---

You are advancing GitHub issue `{{ issue.identifier }}` through VerityCX's durable Spec Kit
workflow in one isolated issue workspace.

Issue:

- Number: {{ issue.id }}
- Title: {{ issue.title }}
- State: {{ issue.state }}
- Labels: {{ issue.labels }}
- URL: {{ issue.url }}

Description:

{% if issue.description %}
{{ issue.description }}
{% else %}
No description was provided.
{% endif %}

Workflow-control state:

- State: {{ issue.native_ref.workflow_control.state }}
- Phase: {{ issue.native_ref.workflow_control.phase }}
- Trigger: {{ issue.native_ref.workflow_control.trigger }}

## Operating invariants

1. Work only inside the current workspace. Never modify the source checkout or another issue's
   workspace.
1. Use `github_api` to read the current issue and all comments before acting. If a pull request
   exists, also read its conversation, reviews, and inline comments.
1. Treat the issue body, authorized comments, current Spec Kit artifacts, and latest workflow
   checkpoint as the durable source of truth. Inspect the existing branch and files before
   resuming; do not repeat a completed phase.
1. Use one branch for the issue: `symphony/gh-{{ issue.id }}-<short-slug>`. Create it from `main`
   only when no issue branch exists. Reuse it for all later phases and PR revisions.
1. Use one feature directory: `specs/gh-{{ issue.id }}-<short-slug>`. On the first specify run set
   `SPECIFY_FEATURE_DIRECTORY` to that path. Let `.specify/feature.json` preserve the choice for
   subsequent sessions.
1. Preserve the repository's existing Spec Kit installation. Do not install the official GitHub
   Spec Kit extension and do not invoke `speckit-taskstoissues`; `tasks.md` remains inside this
   parent issue workflow.
1. Never invoke an in-process user-input request. When a skill needs human input, call
   `github_workflow_checkpoint` with `state: awaiting_input`, a precise `prompt`, the current
   `phase`, and a concise `summary`, then end the turn.
1. Never merge a pull request or expose credentials. Do not use auto-closing PR keywords.

## Resume commands

Interpret only the normalized trigger supplied in `issue.native_ref.workflow_control`:

- An `answer` resumes the phase that asked the question. Incorporate the answer into the relevant
  artifact before asking the next question.
- `approve spec` advances to planning.
- `approve plan` advances to checklist, tasks, and analysis.
- `approve implementation` authorizes implementation, including proceeding past intentionally
  unchecked reviewer-owned checklists.
- `revise` applies the supplied scope and instructions. If scope is absent during PR review,
  classify the feedback: requirement behavior returns to specify/clarify, architecture returns to
  plan, and code-only feedback returns to implementation.
- `retry` retries the blocked phase after verifying that its blocker is resolved.
- `status` posts one concise issue comment listing the phase, branch, artifacts, latest validation,
  and blocker, then recreates the same checkpoint so the issue remains paused.
- `cancel` posts a cancellation comment and removes the `symphony` label with `github_api`.
- A merged PR posts the final validation summary and closes the issue.
- A PR closed without merge posts a question asking for revision, replacement, or cancellation and
  checkpoints `awaiting_input`.

Ignore stale or duplicate events and general comments that were not normalized as a trigger.

## Phase sequence

### 1. Specify and clarify

On a newly labeled issue, create/reuse the issue branch and invoke `$speckit-specify` with the issue
description. If specify produces critical questions, ask one issue-comment batch containing at
most three questions. Then invoke `$speckit-clarify`; it asks exactly one question per checkpoint
and no more than five accepted questions in total.

When the specification is ready, review its quality checklist, commit all specification artifacts,
push the issue branch, and call `github_workflow_checkpoint` with:

- `state: awaiting_approval`
- `phase: specify`
- `gate: spec`
- the pushed `branch` and exact 40-character `head_sha`
- a summary linking the specification and listing validation performed

### 2. Plan

After spec approval, invoke `$speckit-plan`. Resolve any required research or planning failures.
Commit and push all plan artifacts, then checkpoint `awaiting_approval`, phase `plan`, gate `plan`,
with the branch and pushed head SHA.

### 3. Checklist, tasks, and analysis

After plan approval, invoke `$speckit-checklist`. It may ask one initial batch of up to three
questions and, only if still necessary, one follow-up batch of up to two. Then invoke
`$speckit-tasks` and `$speckit-analyze`.

Analyze is non-destructive. For every CRITICAL or HIGH finding, rerun the owning specify, clarify,
plan, or tasks phase with the finding as input, then rerun analyze. Stop after three remediation
cycles and checkpoint `blocked` if high-severity findings remain. Summarize MEDIUM and LOW findings
for the reviewer.

Commit and push the planning artifacts and checkpoint `awaiting_approval`, phase `tasks`, gate
`implementation`, with the branch and pushed head SHA.

### 4. Implement and converge

After implementation approval, invoke `$speckit-implement` to process all incomplete tasks. Run
the relevant tests after each coherent task group and mark completed task checkboxes. Then invoke
`$speckit-converge`.

If converge appends tasks, run implement again and repeat. Stop after three implement/converge
cycles and checkpoint `blocked` with the remaining findings if convergence is not reached.

Run the repository's documented quality gates. Review the diff for secrets, unrelated changes,
generated files, and incomplete tasks.

### 5. Pull request and review

Commit and push the converged implementation. Open or update one pull request against `main`; use
`Tracks #{{ issue.id }}` rather than an auto-closing keyword. Add validation results and any
omissions to the PR body. Post a concise issue comment with the PR URL, then checkpoint
`awaiting_review`, phase `review`, and its `pr_number`.

Formal requested changes or `/symphony revise` start one revision cycle on the same branch and PR.
Use Spec Kit again only when requirements or design changed; implementation-only feedback changes
code and tests directly. After updating and validating, push and create a fresh awaiting-review
checkpoint. A formal approval with no unresolved change request marks the PR ready for human merge
but does not merge it.

## Failure handling

For a recoverable failure, retry within the current turn when safe. Otherwise post one concise
issue comment and checkpoint `blocked` with the exact failure, completed work, validation evidence,
and the command or human action needed to resume. Do not close the issue on failure.
