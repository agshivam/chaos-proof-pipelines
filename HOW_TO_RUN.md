# How to run chaos-proof pipelines

Everything runs on your computer with free tools. No account is needed.

## Before you start

| Tool | Check with | Needed |
| --- | --- | --- |
| Python | `python --version` | 3.10 or newer |
| Git | `git --version` | any |

## Quick start: see the monitor in 3 minutes

```bash
git clone https://github.com/agshivam/chaos-proof-pipelines.git
cd chaos-proof-pipelines
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The browser opens at http://localhost:8501 with the results of the last run, which are stored in `app_data/`.

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

You should see `16 passed`. Every fault has its own test, and there are tests for reruns, backfills and late files.

## Inject every fault and refresh the monitor

```bash
python scripts/run_chaos_suite.py
```

You should see `ALERT:` lines, one per fault, then `PASS: every fault caught by the expected rule, reruns left no duplicates`. This rewrites the files in `app_data/`. Reload the monitor to see the new numbers.

## Try it by hand

```bash
python - <<'PY'
import sys; sys.path.insert(0, "src")
from datetime import date
from pathlib import Path
from chaos.generator import generate_day
from chaos.faults import inject
from chaos.pipeline import connect, run_day
inc = Path("data/incoming"); con = connect(Path("data/chaos.duckdb"))
d = date(2026, 11, 1)
generate_day(d, inc)
inject("bad_category", inc, d)          # try: duplicate_rows, null_key, schema_rename, silent_truncate ...
print(run_day(d, inc, con, Path("data/quarantine")))
PY
```

The result says `rejected` and names the rule. The bad file is copied to `data/quarantine/`.

## Orchestrate with Dagster (optional)

```bash
pip install -r requirements-dev.txt
dagster dev -f orchestration/definitions.py
```

Open http://localhost:3000, choose the `orders` asset, select a few partitions and click **Materialize**. Select the same partitions again to see that a rerun changes nothing.

## Alerts on your phone (optional)

1. In Telegram, talk to `@BotFather`, send `/newbot` and copy the token.
2. Send any message to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `chat` `id`.
3. Run with the values set:
   ```bash
   export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
   python scripts/run_chaos_suite.py
   ```
Never put the token in a file that you commit.

## Deploy the monitor for free

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Create app: repo `agshivam/chaos-proof-pipelines`, branch `main`, file `app/streamlit_app.py`. Deploy.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `No results yet` in the app | Run `python scripts/run_chaos_suite.py` |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt` |
| `test_dagster` is skipped | Install Dagster with `pip install -r requirements-dev.txt` |
| Port 8501 is busy | Run `streamlit run app/streamlit_app.py --server.port 8502` |
