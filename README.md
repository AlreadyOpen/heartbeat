# heartbeat

Starts AlreadyOpen's frequent jobs on time. GitHub's own `schedule` trigger can be late by hours or dropped under load (its docs
say so), so an outside clock calls this repo every 5 minutes and this repo starts whatever is due.

```
cron-job.org (every 5 min) --one token, this repo only--> tick.yml --GitHub App token, 1 h--> due workflows in schedules.json
```

- **Add a job:** one line in `schedules.json` (`repo`, `workflow`, `every_minutes`), plus the repo in the App's installation.
  No new token, no new cron-job.org job.
- **Due rule** (`tick.py`): a workflow starts when its last run, started by anything, began at least `every_minutes` ago
  (less 3 minutes of slack). So a pipeline's own GitHub schedule stays as the backup without double runs; each pipeline's
  `concurrency` group also keeps runs from overlapping.
- **Tokens:** the App token is minted per tick by `actions/create-github-app-token` (1 hour, revoked at the end of the job,
  limited to the listed repos and `actions: write`). The only long-lived secret outside GitHub is cron-job.org's token, which
  can start or cancel runs of this repo and nothing else.
- `python3 tick.py selftest` checks the timing rule (CI runs it on every push).

## Setup (Helen; accounts and keys are never handled by an agent)

1. **GitHub App** (AlreadyOpen org → Settings → Developer settings → GitHub Apps → New):
   name e.g. `alreadyopen-heartbeat`; homepage this repo; Webhook **off**; Repository permissions: **Actions: Read and write**
   (Metadata: read is added automatically); nothing else; "Only on this account". Create it, then **Install** it on the
   AlreadyOpen org with **Only select repositories**: the repos in `schedules.json`.
2. **Client ID** (shown on the App page, not secret): `gh variable set APP_CLIENT_ID -R AlreadyOpen/heartbeat --body <client id>`
3. **Private key**: on the App page, "Generate a private key" downloads a `.pem`. Then
   `gh secret set APP_PRIVATE_KEY -R AlreadyOpen/heartbeat < ~/Downloads/<file>.pem` and delete the `.pem`.
4. **cron-job.org token**: GitHub → Settings → Developer settings → Fine-grained tokens → Generate: resource owner
   AlreadyOpen, **Only select repositories: heartbeat**, Repository permissions **Actions: Read and write**, an expiry
   (e.g. 1 year; GitHub emails before it expires). The org may need to approve it.
5. **cron-job.org job**: every 5 minutes, method **POST**,
   URL `https://api.github.com/repos/AlreadyOpen/heartbeat/actions/workflows/tick.yml/dispatches`,
   headers `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`,
   body `{"ref":"main"}`. GitHub answers `204` with no body.

Set up 2026-10-11: App `alreadyopen-heartbeat` (installed on sa-transit and world-flights), token expires
**2027-10-12**. On renewal, also move `X-GitHub-Api-Version` to the newest version
(https://docs.github.com/en/rest/about-the-rest-api/api-versions): GitHub deprecated `2022-11-28`, sunset 2028-03-10.
A new pipeline needs its line in `schedules.json` and its repo added to the App's installation.

Check: `gh run list -R AlreadyOpen/heartbeat -w tick` shows a run every 5 minutes; the pipelines' `live` runs show
`workflow_dispatch` every 15.
