---
tracker:
  kind: github
  provider:
    repo: rohanyupadhyay/VerityCX
    token: $GITHUB_TOKEN
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
  thread_sandbox: workspace-write
  turn_sandbox_policy:
    type: workspaceWrite
    networkAccess: true
---

You are implementing GitHub issue `{{ issue.identifier }}` in an isolated VerityCX workspace.

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

Work autonomously and only inside the current repository copy. Do not touch the source checkout or
any other workspace. Preserve the repository's existing Spec Kit files and workflow unless the
issue explicitly requires changing them.

1. Use `github_api` to fetch the issue and its comments before starting. Treat the current issue
   body, acceptance criteria, and comments as the source of truth.
2. Read the repository instructions and inspect the current state before editing. Keep the change
   narrowly scoped to the issue.
3. Create a branch from the current default-branch checkout named
   `symphony/gh-{{ issue.id }}-<short-description>`.
4. Reproduce or otherwise establish the requested behavior before implementation when applicable.
5. Implement the change and run the repository's relevant checks. Run the full documented quality
   gate when practical; explain any omitted check in the pull request.
6. Review the diff for unrelated or generated changes. Commit the finished work with a clear
   message, push the branch, and open a pull request against `main`. Do not merge the pull request.
   Refer to the issue as `Tracks #{{ issue.id }}` rather than using an auto-closing keyword.
7. Use `github_api` to add one concise issue comment containing the pull-request URL and validation
   results. Then close the issue so Symphony treats this orchestration run as complete; the pull
   request remains the human review queue.

Do not close the issue if implementation, validation, push, or pull-request creation failed. In
that case, add one concise issue comment describing the blocker and leave the issue open for human
attention. Never expose credentials in commands, logs, commits, comments, or pull requests.
