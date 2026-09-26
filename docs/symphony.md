<!-- Documents the GitHub issue interface for VerityCX's Symphony automation. -->

# Symphony for VerityCX

GitHub issues are the workflow UI. Symphony's local dashboard shows running agents, logs, retries,
and token usage; it is not where requirements are approved.

## Start Symphony

Build the reusable [Symphony Plus fork](https://github.com/rohanyupadhyay/symphony-plus), create an
operator-owned private GitHub App profile once, and launch it with the repository-owned workflow:

```bash
cd /home/rohan/code/symphony-plus/elixir
mise exec -- mix setup
mise exec -- mix build
./bin/symphony github-app setup rohanyupadhyay/VerityCX --profile veritycx
./bin/symphony github-app verify rohanyupadhyay/VerityCX --profile veritycx
./scripts/run-github --app-profile veritycx /home/rohan/code/VerityCX/WORKFLOW.md --port 4000
```

The setup command opens GitHub with the required Contents, Issues, Pull requests, and Workflows
write permissions and webhooks disabled. Generate a private key, install the App only on VerityCX,
and enter the App ID, installation ID, and downloaded PEM path. The resulting `veritycx` profile
lives under `~/.config/symphony-plus/github-apps/` with private file permissions; it is not part of
this repository.

Open `http://localhost:4000` for runtime status. The launcher supplies App identifiers and the key
path only to the Symphony host. Symphony mints short-lived installation tokens and removes all App
credentials from Codex. GitHub comments, labels, PRs, and pushes appear as the selected App's
`<slug>[bot]` identity.

## Start, inspect, and stop work

- Open with no `symphony` label: not started; Symphony ignores it.
- Open with the `symphony` label: authorized to run or waiting at a checkpoint.
- Remove the label: stop/cancel future execution.
- Closed: terminal; Symphony removes the issue workspace during cleanup. If cancellation removed
  the label before the issue was closed, startup recovery performs this terminal cleanup.

Each issue uses `/home/rohan/code/symphony-workspaces/VerityCX/GH-<number>`, one branch named
`symphony/gh-<number>-<slug>`, and one directory named `specs/gh-<number>-<slug>`. Specify, clarify,
plan, tasks, implementation, convergence, and PR revisions all reuse them.

The workflow gives its Codex agents `danger-full-access` inside those dedicated issue workspaces.
This is necessary because Codex's narrower `workspace-write` sandbox makes `.git` read-only and
would prevent Symphony from creating the required issue branch or commits. Do not point
`workspace.root` at this checkout or another developer working tree. This setting does not change
the sandbox used by ordinary Codex sessions outside Symphony.

Agents create commits locally with the App bot identity and call the host-authenticated
`github_git_push` tool. Direct `git push` is not part of this workflow. App-authenticated pushes
currently require local workspaces; SSH workers must use the legacy external credential path.

Do not add the label to issue #1 while its work remains deferred. Use a separate issue when testing
the integration.

## Conversation commands

When Symphony asks a direct question, reply normally in the issue. At approval and review gates,
use an explicit command:

```text
/symphony approve spec
/symphony approve plan
/symphony approve implementation
/symphony revise [spec|plan|implementation] <instructions>
/symphony retry
/symphony status
/symphony cancel
```

Commands and answers are accepted from repository owners, organization members, and collaborators.
General comments do not start revision work. On a PR, a formal “Request changes” review or explicit
`/symphony revise` triggers work; ordinary conversation and inline comments are collected as
context. Approval never merges automatically.

The issue remains open after the PR opens. Symphony closes it only after GitHub reports the PR
merged. If the PR closes without merge, the issue remains open and asks whether to revise, replace,
or cancel.

## Spec Kit boundary and recovery

This workflow uses VerityCX's repository-local Spec Kit 1.0.11 skills. It does not install the
official GitHub Spec Kit extension and does not convert `tasks.md` into child GitHub issues.

Questions and pauses are stored as versioned hidden markers in ordinary GitHub comments. After a
restart, Symphony reconstructs the latest phase and processed-event cursors from GitHub and reuses
the existing workspace. No workflow database is required.

The integration polls every 30 seconds. An issue awaiting PR review makes additional requests for
the PR conversation, inline comments, formal reviews, and merge state. If many issues are labeled
simultaneously, increase the polling interval and monitor GitHub API rate limits.

Polling, manual startup, and the local dashboard remain intentional. Webhooks, automatic daemon
startup, and the official Spec Kit GitHub extension remain deferred. Legacy PAT authentication is
available in Symphony Plus for compatibility but is not the VerityCX default.
