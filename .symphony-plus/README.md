<!-- Documents the GitHub issue interface for VerityCX's Symphony Plus automation. -->

# Symphony Plus for VerityCX

GitHub issues are the workflow UI. Symphony Plus's local dashboard shows projects, running agents,
logs, retries, quota waits, blocked work, and token usage. Requirements are approved in GitHub.

This setup follows Symphony Plus revision `16283fc` (2026-10-24) and the current reusable GitHub
workflow conventions. Spec, plan, and implementation require explicit approval. Completed
implementations enter automatic PR review and the host-owned serialized merge queue, configured in
[WORKFLOW.md](WORKFLOW.md). Human PR approval is not required; human change requests suspend work
until dismissed.

## Update and verify the host installation

Use the external [Symphony Plus checkout](https://github.com/rohanyupadhyay/symphony-plus). Inspect
its working tree and remotes first; update a clean default branch with a fast-forward-only pull.
Do not discard local work or update a running installation underneath active agents.

```bash
cd /home/rohan/code/symphony-plus
git status --short
git remote -v
git pull --ff-only fork main
cd elixir
mise trust
mise install
mise exec -- mix setup
mise exec -- mix build
```

The current executable is `bin/symphony-plus`. Reuse the existing operator-owned `veritycx` App
profile and verify its repository access:

```bash
mise exec -- ./bin/symphony-plus github-app verify rohanyupadhyay/VerityCX --profile veritycx
```

Only if that profile is absent, the operator creates it with:

```bash
mise exec -- ./bin/symphony-plus github-app setup rohanyupadhyay/VerityCX --profile veritycx
```

Setup opens GitHub with Contents, Issues, Pull requests, and Workflows write permissions and
webhooks disabled. The operator creates or selects the private App, generates its key, installs it
on VerityCX, and enters the requested values directly in the terminal. Profiles stay under
`~/.config/symphony-plus/github-apps/` with private permissions, outside this repository.

The host also needs Git, Codex CLI, uv, and PowerShell (`pwsh`): this repository's existing Spec Kit
1.0.11 skills invoke PowerShell scripts. Preserve that installation and its templates.

## Register with the service

Projects own their workflow and operator guide; the external installation owns App profiles,
runtime data, updates, and the project registry. Register an absolute workflow path through the
dashboard or CLI. Do not copy the workflow into the installation or commit a registry in VerityCX.
The current CLI supports starting a service with zero projects and adding projects without restart.

Reuse an existing service when its App profile has verified access to VerityCX. One service uses
one host App environment; adding a project does not load another profile. Set `--service-url` to
that service's URL and use its data root when listing projects. Do not register the same
repository/workspace root with two services.

The host's existing `symphony-plus` App profile currently fails verification for VerityCX; its
`veritycx` profile verifies successfully. Until the operator grants a shared App installation
access and verifies it, use the `veritycx` profile with a separate data root as below. App
installation and permission changes belong to the operator.

Start that App-authenticated service once from the external installation. In a second terminal,
register the workflow. Both terminals use the same Elixir directory:

```bash
cd /home/rohan/code/symphony-plus/elixir
mise exec -- ./scripts/run-github --app-profile veritycx --data-root ./tmp/veritycx --port 4000
```

```bash
cd /home/rohan/code/symphony-plus/elixir
mise exec -- ./bin/symphony-plus projects add /home/rohan/code/VerityCX/.symphony-plus/WORKFLOW.md --service-url http://localhost:4000
mise exec -- ./bin/symphony-plus projects list --data-root ./tmp/veritycx --format json
```

Open `http://localhost:4000` for project/runtime status; `/api/v1/state` exposes runtime state.
Registration is idempotent and persists in the installation-local data root across restarts. The
registry stores workflow paths, not credentials. A missing or invalid workflow remains registered
and is retried when repaired.

The dedicated data root above keeps the `veritycx` profile separate from another service using a
different App profile. Passing a positional workflow at startup remains a compatibility path;
registration through `projects add` is the convention for ongoing project management.

The launcher supplies App identifiers and the key path only to the host. Symphony Plus mints
short-lived installation tokens and removes App/PAT credentials from Codex. GitHub changes appear
as the selected App's `<slug>[bot]` identity. Agents commit locally and push through the
host-authenticated `github_git_push` tool; App-authenticated pushes require local workspaces.

## Migration from the previous setup

The tool directory is now `.symphony-plus/`, the dispatch label is `symphony-plus`, commands begin
with `/symphony-plus`, and new branches use `symphony-plus/gh-<number>-<slug>`. The old `symphony`
label no longer starts work. Reconcile the new label without labeling existing issues:

```bash
gh label create symphony-plus --repo rohanyupadhyay/VerityCX --description "Ready for autonomous Symphony Plus execution" --color 1D76DB --force
```

Before replacing an old service, record its PID, workflow path, data root, port, and waiting work;
stop it cleanly. Remove its old workflow registration only when idle and without retained work,
then add the new path. `projects remove` refuses retained work and never deletes source files or
issue workspaces. Never edit registry JSON to bypass that check.

The old workspace root was `/home/rohan/code/symphony-workspaces/VerityCX`; it was empty at migration.
New work uses `/home/rohan/code/symphony-plus-workspaces/VerityCX`. If restoring an older installation
with retained issue workspaces, keep its original root and existing branch until that work finishes;
do not rename or delete active workspaces or restart an issue from scratch.

## Start, inspect, and stop work

- Open without `symphony-plus`: ignored.
- Open with `symphony-plus`: authorized to run or waiting at a checkpoint.
- Remove the label: stop future dispatch.
- Closed: terminal; cleanup removes the issue workspace. If cancellation removed the label first,
  startup recovery performs terminal cleanup after closure.

Each issue uses `/home/rohan/code/symphony-plus-workspaces/VerityCX/GH-<number>`, one branch named
`symphony-plus/gh-<number>-<slug>`, and one directory named `specs/gh-<number>-<slug>`. All eight Spec
Kit phases and PR revisions reuse them. Existing branches and artifacts remain authoritative.

Codex runs with `danger-full-access` because `workspace-write` protects `.git` and prevents the
required branches and commits. Use this only on a trusted host with dedicated issue workspaces;
this sandbox mode is not a filesystem security boundary. Never point `workspace.root` at a
source/developer checkout. It does not change ordinary Codex sessions outside Symphony Plus.

Do not start deferred issue #1. Use a separate issue for any explicitly authorized smoke test.

## Conversation commands

Reply normally to a direct question. Use an explicit command at approval and review gates:

```text
/symphony-plus approve spec
/symphony-plus approve plan
/symphony-plus approve implementation
/symphony-plus revise [spec|plan|implementation] <instructions>
/symphony-plus retry
/symphony-plus status
/symphony-plus cancel
```

Commands and answers are accepted from owners, members, and collaborators. General comments and
inline PR comments are context, not triggers. `/symphony-plus revise` requests another cycle when
no human change request is active. Requirements or architecture changes re-enter the corresponding
Spec Kit phase and approval gate.

New managed PRs use `review_pending` with the PR number, branch, and exact pushed head SHA. The host
validates provenance, applies the dispatch label to the PR, and automatically starts review on the
next poll. Review repairs in-scope findings and target-branch conflicts, reruns project checks, and
returns any changed head to a fresh review. A successful review of an unchanged head records
`merge_queued` with the repository, target branch, exact reviewed head, and prerequisite PR numbers.
The host supplies queue order and performs the guarded final merge after checking the current
candidate, target, checks, and policy. Agents never call the merge endpoint directly.

Human PR approval is not a queue prerequisite. A current human `CHANGES_REQUESTED` review suspends
all automatic review, branch updates, and queue mutations until dismissed; it does not trigger a
repair cycle. Merge conflicts, changed heads, and `merge_update_required` outcomes resume review
and repair automatically. Older `awaiting_review` checkpoints remain readable for recovery, but
new handoffs use `review_pending`.

Every checkpoint begins with a `Spec Kit progress` report naming all eight phases. It records run
counts, question counts for this run and the issue total, retained answers and sources, checklist
choices and sources, material assumptions, remediation/convergence cycles, validation omissions,
and the next phase. Retries and status requests neither reset totals nor repeat resolved questions.

Checklist focus defaults to the two highest-risk requirement areas, depth to standard review
adjusted for risk, and audience to PR reviewers. Explicit authorized choices override defaults and
persist across retries. Missing checklist preferences alone no longer pause the issue. Questions
resolve consequential requirements or policy ambiguity; they appear once, in the checkpoint prompt
before the phase report. Spec, plan, and implementation approval gates still apply.

Every PR body keeps exactly one plain `Tracks #<number>` line. It never uses an auto-closing keyword.
The issue stays open until the workflow observes the PR merged, posts final validation, and closes
it explicitly. Closure without merge asks whether to revise, replace, or cancel.

## Recovery, quota waits, and updates

Versioned hidden markers in GitHub comments preserve phases and processed-event cursors. Restart
reconstructs checkpoints and reuses existing workspaces. Recognized Codex usage exhaustion produces
a durable quota wait and resumes the same native thread after renewal; a thread that cannot resume
blocks for operator action. Quota-waiting and blocked are distinct dashboard states.

Polling remains 30 seconds. Waiting review issues need additional PR feedback and merge-state
requests. Increase the interval and monitor API limits if many issues run together.

Automatic source updates are disabled by default. They are installation-wide host policy; this
project does not opt a shared installation into updates. Enabling them requires a clean attached
canonical source checkout, disjoint installation/workspace roots, and a supervisor for
`scripts/run-github`. The updater prepares the candidate, drains new dispatch without interrupting
active work or continuations, and activates only when safe and idle. See the
[upstream update guide](https://github.com/rohanyupadhyay/symphony-plus/blob/main/elixir/README.md#automatic-source-updates)
for configuration and blocked-update recovery. Do not reset or rebase to clear a blocked update.

Webhooks, automatic daemon startup, and remote-worker App secret brokering remain outside this
setup. The official GitHub Spec Kit extension is not installed; `speckit-taskstoissues` is not used.
