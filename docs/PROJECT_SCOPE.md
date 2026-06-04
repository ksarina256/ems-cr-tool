# ClearCase to Git/Gitea Snapshot Mirror Scope

## Goal

Make the current ClearCase master and dev branch/view states easy for the team to compare in Git/Gitea.

The first version is a repeatable snapshot mirror, not a full ClearCase history reconstruction. It focuses on the files currently visible in configured ClearCase views and pushes those files to Git branches such as `cc-master` and `cc-dev`.

## Working Assumptions

- The ClearCase setup is base ClearCase unless the team later confirms UCM.
- The build/ClearCase machine is the right place to run the tool because it has `cleartool` and view access.
- Deleted historical files and CR-by-CR reconstruction are out of scope for V1.
- Current snapshot accuracy is in scope: files not present in the current visible source tree are removed from the mirror branch on refresh.
- Gitea remains the place where the team reviews full line-by-line diffs.

## Repositories

- Tool repo: contains this application and tests.
- Mirror repo: receives ClearCase snapshots as Git branches and is pushed to Gitea.

Example mirror branches:

- `cc-master`: current visible files from the ClearCase master view.
- `cc-dev`: current visible files from the ClearCase dev view.

## Team Workflow

1. A maintainer deploys this tool once on the ClearCase/build server.
2. Teammates open the internal web UI.
3. They click `Refresh Snapshot` for master, dev, or all configured branches.
4. The backend enters the configured ClearCase view, copies the configured VOB/project path, commits the snapshot to Git, and optionally pushes to Gitea.
5. Teammates click `Run Compare` or open the Gitea compare link.

## Maintainer Responsibilities

- Configure the ClearCase view names.
- Configure the source VOB/project path.
- Configure the local mirror repo path.
- Configure the Gitea remote URL and optional web URL.
- Maintain exclude patterns for generated files.
- Run or deploy the web UI on a server with `cleartool` and Git.

## Team User Responsibilities

- Open the web UI.
- Refresh snapshots.
- View comparison summaries and Gitea diffs.

Team users should not edit config files or run ClearCase commands directly.

## V1 Commands

```bash
python3 -m ccgit.cli --config ccgit.json validate
python3 -m ccgit.cli --config ccgit.json snapshot master --push
python3 -m ccgit.cli --config ccgit.json snapshot dev --push
python3 -m ccgit.cli --config ccgit.json snapshot all --push
python3 -m ccgit.cli --config ccgit.json compare --base master --target dev --write
python3 -m ccgit.cli --config ccgit.json web --host 0.0.0.0 --port 8080
```

If installed with `pip`, use `ccgit` instead of `python3 -m ccgit.cli`.

## Config

Copy `ccgit.example.json` to `ccgit.json` and update:

- `local_repo`
- `gitea_repo`
- `gitea_web_url`
- `branches.master.view`
- `branches.dev.view`
- `branches.*.source_path`
- `exclude`

For dynamic ClearCase views, use `copy_mode: "setview"`.

For snapshot views or tests where the source path is directly readable, use `copy_mode: "direct"` and omit `view`.

## Acceptance Criteria

- The tool runs on Python 3.
- The tool can refresh master/dev snapshots from configured ClearCase views.
- The mirror repo contains separate Git branches for master and dev snapshots.
- A refresh with no source changes does not create an unnecessary commit.
- The compare report excludes the tool's own `.ccgit/` metadata.
- The web UI can trigger refreshes and comparisons without teammates editing files.
- Tests can be run without ClearCase installed.

## Known V1 Limitations

- Does not reconstruct every historical ClearCase version as Git commits.
- Does not import deleted historical files.
- Does not parse CRs or UCM activities into Git commits.
- Uses Gitea for detailed line-by-line diffs instead of reimplementing a diff viewer.
- Web authentication should be handled by network controls, reverse proxy, or a future auth layer before broad deployment.
