---
tracker:
  kind: github
  provider:
    repo: rohanyupadhyay/VerityCX
    auth:
      kind: github_app
      app_id: $GITHUB_APP_ID
      installation_id: $GITHUB_APP_INSTALLATION_ID
      private_key_path: $GITHUB_APP_PRIVATE_KEY_PATH
    workflow_control:
      enabled: true
      authorized_associations:
        - OWNER
        - MEMBER
        - COLLABORATOR
  required_labels:
    - symphony-plus
  active_states:
    - open
  terminal_states:
    - closed
polling:
  interval_ms: 30000
merge_queue:
  enabled: true
  poll_interval_ms: 30000
  max_retry_backoff_ms: 300000
workspace:
  root: /home/rohan/code/symphony-plus-workspaces/VerityCX
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
  # Agents need to create issue branches and commits; workspace-write protects .git.
  # Use only on a trusted host with dedicated issue workspaces: danger-full-access
  # is not a filesystem security boundary.
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
   exists, also read its conversation, reviews, inline comments, current-head checks, and merge state.
1. Apply `.specify/memory/constitution.md` during planning, analysis, implementation, and review.
   Preserve the repository's data-use policy and document any justified exception.
1. Create commits locally, then call `github_git_push` with the exact issue branch and local
   40-character `HEAD`. Never run `git push` directly. The host tool validates the workspace,
   clean tree, branch, SHA, and remote before using GitHub App authentication.
1. Treat the issue body, authorized comments, current Spec Kit artifacts, and latest workflow
   checkpoint as the durable source of truth. Inspect the existing branch and files before
   resuming; do not repeat a completed phase.
1. Use one branch for the issue: `symphony-plus/gh-{{ issue.id }}-<short-slug>`. Create it from `main`
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
1. Never call GitHub's merge endpoint directly, expose credentials, or use auto-closing PR keywords.
   Only the host-owned serialized merge queue performs the guarded final merge after a successful
   automatic review of the exact managed head.

## Required checkpoint phase report

Every `github_workflow_checkpoint` summary is an operator-facing audit record. Begin it with this
exact structure and fill every field; use `none` or `not run` instead of omitting a field:

```text
### Spec Kit progress
- Phases:
  - specify: <completed | not run | skipped: reason; run count; outcome>
  - clarify: <completed | not run | skipped: reason; run count; outcome>
  - plan: <completed | not run | skipped: reason; run count; outcome>
  - checklist: <completed | not run | skipped: reason; run count; outcome>
  - tasks: <completed | not run | skipped: reason; run count; outcome>
  - analyze: <completed | not run | skipped: reason; run count; outcome>
  - implement: <completed | not run | skipped: reason; run count; outcome>
  - converge: <completed | not run | skipped: reason; run count; outcome>
- Current checkpoint: <waiting state, phase, and approval gate when applicable>
- Questions asked this run: <count by specify, clarify, and checklist; explain every zero>
- Questions asked total: <cumulative distinct questions by specify, clarify, and checklist>
- Checklist choices: <focus, depth, audience, and the source of each choice; or not run>
- Answers retained: <resolved question, selected value, and authorized comment reference; or none>
- Assumptions adopted: <material defaults inferred without an answer, or none>
- Analyze cycles: <count, findings, and remediations, or not run>
- Convergence cycles: <count and tasks appended, or not run>
- Validation: <checks performed and omissions>
- Next phase: <what an answer or approval will run>
```

Never omit a phase from the ledger or claim that a phase ran when it was skipped. Mark every phase
as `completed`, `not run`, or `skipped: <reason>`, including its cumulative run count and outcome,
rather than collapsing phases into broad labels such as “planning” or “implementation.” If a phase
asks zero questions, record `zero questions` and the concrete reason. Include the same report in `awaiting_input`, `blocked`,
`awaiting_approval`, `review_pending`, `merge_queued`, `/symphony-plus status`, and final merged-PR comments.

Reconstruct question totals and resolved answers from authorized comments, artifacts, and prior
checkpoints on every resume. A retry, status request, or repeated rendering adds no new question
and never resets the issue total. Retain selected values and their sources until an authorized
revision changes them; do not replace an explicit answer with a newly inferred default.

For `awaiting_input`, put the complete question batch only in the checkpoint's `prompt` field.
The host renders that prompt before the phase report. Keep the summary to the report, decisions,
and evidence; publish the checkpoint once rather than also posting the questions with `github_api`.
Use descriptive option names, mark the recommendation, and make example replies select the
recommended values. Explain how each choice changes the result.

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
- `automatic_review` reviews and repairs the managed PR at the trigger's exact `head_sha`.
  A `merge_update_required` outcome resumes this review-and-repair cycle automatically.
- `status` posts one concise issue comment listing the phase, branch, artifacts, latest validation,
  and blocker, then recreates the same checkpoint so the issue remains paused.
- `cancel` posts a cancellation comment and removes the `symphony-plus` label with `github_api`.
- A merged PR posts the final validation summary and closes the issue.
- A PR closed without merge posts a question asking for revision, replacement, or cancellation and
  checkpoints `awaiting_input`.

Ignore stale or duplicate events and general comments that were not normalized as a trigger.
At an `awaiting_input` checkpoint, `/symphony-plus status` and `/symphony-plus cancel` are commands,
not answers. Older `awaiting_review` checkpoints remain readable for recovery; new PR handoffs use
`review_pending`.

## Phase sequence

### 1. Specify and clarify

On a newly labeled issue, create/reuse the issue branch and invoke `$speckit-specify` with the issue
description. If specify produces critical questions, put one batch of at most three questions in
the `awaiting_input` checkpoint prompt and end the turn. Then invoke `$speckit-clarify`; it asks
exactly one question per checkpoint and no more than five accepted questions in total. Clarify may
ask zero only when its structured
scan finds no material ambiguity; record that outcome and its concrete reason in the phase report.

When the specification is ready, review its quality checklist, commit all specification artifacts,
call `github_git_push`, and then call `github_workflow_checkpoint` with:

- `state: awaiting_approval`
- `phase: specify`
- `gate: spec`
- the pushed `branch` and exact 40-character `head_sha`
- a structured phase report naming `specify` and `clarify` separately, their question counts,
  every material assumption adopted, a link to the specification, and validation performed

### 2. Plan

After spec approval, invoke `$speckit-plan`. Resolve any required research or planning failures.
Commit all plan artifacts, call `github_git_push`, then checkpoint `awaiting_approval`, phase
`plan`, gate `plan`, with the branch and pushed head SHA. Its phase report must name `plan`, retain
the earlier interaction totals and assumptions, and identify `checklist` as the next phase.

### 3. Checklist, tasks, and analysis

After plan approval, resolve checklist focus, depth, and audience from explicit authorized input
and previously recorded choices first. For missing choices, use these repository defaults:

- Focus: the two highest-risk requirement areas in the issue and approved specification/plan,
  including data-use policy or data preservation when relevant.
- Depth: standard review; use lightweight coverage for low-risk documentation changes or formal
  coverage for high-risk lifecycle, concurrency, or data-preservation changes, with a recorded reason.
- Audience: PR reviewer.

Pass the resolved choices explicitly to `$speckit-checklist`, which skips intent questions already
answered by its arguments. Record each choice and its source in the phase report. Continue without
an input checkpoint solely to configure this internal review artifact. Ask only when unresolved
ambiguity materially affects scope, observable behavior, acceptance criteria, compatibility, data
preservation, or policy; route those questions to specify/clarify with its existing limits and gates.
Missing checklist preferences alone do not require input. Report zero questions when defaults or
retained answers suffice, including the reason. Then invoke `$speckit-tasks` and `$speckit-analyze`.

Analyze is non-destructive. For every CRITICAL or HIGH finding, rerun the owning specify, clarify,
plan, or tasks phase with the finding as input, then rerun analyze. Stop after three remediation
cycles and checkpoint `blocked` if high-severity findings remain. Summarize MEDIUM and LOW findings
for the reviewer.

Commit the planning artifacts, call `github_git_push`, and checkpoint `awaiting_approval`, phase
`tasks`, gate `implementation`, with the branch and pushed head SHA. Its phase report must name
`checklist`, `tasks`, and `analyze` separately, record checklist questions and answers, and state
the analyze cycle count and findings by severity.

### 4. Implement and converge

After implementation approval, invoke `$speckit-implement` to process all incomplete tasks. Run
the relevant tests after each coherent task group and mark completed task checkboxes. Then invoke
`$speckit-converge`.

If converge appends tasks, run implement again and repeat. Stop after three implement/converge
cycles and checkpoint `blocked` with the remaining findings if convergence is not reached.

Run the repository's documented quality gates from the issue workspace:

```bash
uv lock --check
uv sync --locked
uv run python scripts/check_environment_contract.py
uv run ruff format --check src scripts tests
uv run ruff check src scripts tests
uv run mypy --strict src scripts tests
uv run pytest tests -m "not support_db and not live"
uv run mdformat --check .symphony-plus/README.md
```

Also run the maintained Markdown/YAML checks in `.github/workflows/quality.yml`. If the change
requires dedicated PostgreSQL integration or live provider checks, use the documented opt-in
procedure and record every omission. Never claim those checks ran when only offline checks ran.
Review the diff for secrets, unrelated changes, generated files, and incomplete tasks.

### 5. Pull request and review

Commit the converged implementation and call `github_git_push`. Open or update one pull request
against `main`; include exactly one plain `Tracks #{{ issue.id }}` line in the body, with no
auto-closing keyword. Preserve that single reference across updates, retries, and revisions. Add
validation results and any omissions to the PR body. Post a concise issue comment with the PR URL,
then checkpoint `review_pending`, phase `review`, with its `pr_number`, issue `branch`, and exact
pushed `head_sha`. The host validates same-repository provenance and the current head, applies the
configured `symphony-plus` label, and records the checkpoint. The next poll starts automatic review
without a human command. Its phase report must name
`implement` and `converge` separately, state the convergence cycle count and whether tasks were
appended, and list every validation omission.

### 6. Automatic review and merge queue

On an `automatic_review` trigger, inspect the complete diff, conversation, formal reviews, inline
comments, merge state, and checks for the current head in this same issue workspace. If any human
review remains `CHANGES_REQUESTED`, make no mutation, post no checkpoint, and end the turn. The host
suspends automatic review, branch updates, and merging until that review is dismissed, then resumes
automatically. A human change request is a suspension signal, not a revision command.

Otherwise reproduce and repair in-scope findings on the same branch. Distinguish PR-caused failures
from external blockers. Resolve target-branch conflicts by merging the latest target into the issue
branch and preserving both changes. A changed head, merge conflict, or `merge_update_required`
outcome resumes review and repair automatically, without asking for human input. Run the targeted
tests and the quality gates in phase 4; call `github_git_push` for any corrections and update the
same PR. Record findings, corrections, current-head checks, validation, and omissions.

If review changes and pushes the branch, post a fresh `review_pending` checkpoint for the new exact
head and end the turn so that revision receives its own complete automatic review. After a successful
review with no mutations or findings remaining, re-read the PR's current head, head branch, base
branch, repository, and any explicitly declared same-repository prerequisite PR numbers. The current
head must equal the `automatic_review` trigger's `head_sha`. If it advanced during review, post a
fresh `review_pending` checkpoint for that head and end the turn.

For a successfully reviewed unchanged head, call `github_workflow_checkpoint` with:

- `state: merge_queued`
- `phase: merge_queue`
- `pr_number`: the managed PR number
- `branch` and exact 40-character `head_sha`: the reviewed issue branch and head
- `repository: rohanyupadhyay/VerityCX`
- `target_branch`: the PR's base branch, normally `main`
- `dependencies`: normalized same-repository prerequisite PR numbers, or `[]`
- `summary`: the complete phase report and review/validation evidence

The host supplies `admission_sequence` from the review trigger. Human PR approval is not required.
End the turn after the durable checkpoint. Only the host-owned queue updates the active queue head,
checks its exact candidate against the current target and repository policy, and performs the merge.
Use `blocked` with a concrete recovery action when required evidence or an external dependency
prevents completion.

`/symphony-plus revise` starts a revision cycle on the same branch and PR when no active human change
request exists. Use Spec Kit again only when requirements or design changed; implementation-only
feedback changes code and tests directly. After updating and validating, call `github_git_push` and
post a fresh `review_pending` checkpoint for automatic review.

After GitHub reports the PR merged, post final validation and close the parent issue explicitly.
If the PR closes without merge, keep the issue open and checkpoint `awaiting_input` with a prompt
asking whether to revise, replace, or cancel. The `Tracks` reference never owns issue closure.

## Failure handling

For a recoverable failure, retry within the current turn when safe. Otherwise post one concise
issue comment and checkpoint `blocked` with the exact failure, completed work, validation evidence,
and the command or human action needed to resume. Do not close the issue on failure.
