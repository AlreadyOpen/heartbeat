"""One heartbeat tick (tick.yml, started every 5 min by cron-job.org): start each workflow in schedules.json whose last run
began at least `every_minutes` ago (less SLACK, so a few seconds of tick jitter never skips a slot). Runs started by anything
else (a pipeline's own GitHub schedule, a manual run) count, so the backup schedules and this never double up.
  python tick.py            needs GH_TOKEN (a GitHub App installation token with actions: write on the listed repos)
  python tick.py repos      prints the repo names, comma-separated (for the token step)
  python tick.py selftest   checks the timing rule, no network"""
import json, os, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

SLACK = 3   # minutes: ticks are 5 min apart, so a 15-min job runs every third tick even when a tick is late
JOBS = json.loads((Path(__file__).parent / 'schedules.json').read_text())


def due(last_start, now, every):
    return last_start is None or (now - last_start).total_seconds() >= (every - SLACK) * 60


def api(path, body=None):
    req = urllib.request.Request(f'https://api.github.com{path}', data=json.dumps(body).encode() if body else None,
                                 method='POST' if body else 'GET',
                                 headers={'Authorization': f'Bearer {os.environ["GH_TOKEN"]}', 'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b'null')


def tick():
    now, failed = datetime.now(timezone.utc), 0
    for j in JOBS:
        name = f"{j['repo']}/{j['workflow']}"
        try:
            runs = api(f"/repos/{j['repo']}/actions/workflows/{j['workflow']}/runs?per_page=1")['workflow_runs']
            last = datetime.fromisoformat(runs[0]['created_at'].replace('Z', '+00:00')) if runs else None
            if not due(last, now, j['every_minutes']):
                print(f'{name}: not due (last run {last:%H:%M:%S})'); continue
            api(f"/repos/{j['repo']}/actions/workflows/{j['workflow']}/dispatches", {'ref': j.get('ref', 'main')})
            print(f'{name}: started')
        except Exception as e:                          # one bad job never stops the others
            failed += 1; print(f'::warning::{name}: {e}')
    sys.exit(1 if failed == len(JOBS) else 0)           # all failing usually means the token or the App is wrong


def selftest():
    t = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    m = lambda x: t.replace(minute=x)
    assert due(None, t, 15)
    assert not due(m(0), m(5), 15) and not due(m(0), m(10), 15)
    assert due(m(0), m(15), 15) and due(m(0), m(12), 15)            # on time, or a tick 3 min early
    assert not due(m(1), m(10), 15) and due(m(1), m(15), 15)       # a late tick: the next one catches up
    for j in JOBS:
        assert j['repo'].startswith('AlreadyOpen/') and j['workflow'].endswith(('.yml', '.yaml')) and j['every_minutes'] >= 5, j
    print(f'selftest ok ({len(JOBS)} jobs)')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'tick'
    if cmd == 'repos':
        print(','.join(sorted({j['repo'].split('/')[1] for j in JOBS})))
    else:
        {'tick': tick, 'selftest': selftest}[cmd]()
