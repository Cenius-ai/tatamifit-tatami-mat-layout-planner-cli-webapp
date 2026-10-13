# Installing TatamiFit

TatamiFit is one standard-library Python file. There is no server, no database, no seed
step and no service to start: "install" only means "make sure Python is present and the
test runner is on hand".

## Prerequisites (system, installed by you, never by the scripts)

| Requirement | Why | Check |
|-------------|-----|-------|
| Python 3.8 or newer | runs the planner | `python3 --version` |
| A terminal 80 columns x 24 rows | the plan page is drawn to that budget | resize if lines wrap |

Nothing else is required — no compiler, no SQLite, no Node, no environment variables and
no configuration file.

## Step 1 — install the project dependencies

```sh
bash install.sh
```

The script:

1. checks the interpreter version,
2. upgrades `pip`, `setuptools` and `wheel` (best effort — safe to re-run),
3. installs `requirements.txt` (only the test runner, `pytest`),
4. installs the optional `tatamifit` console command (`pip install -e .`),
5. imports the planner as a self-check,
6. **exits**. It never starts the planner and never writes state.

It only uses the Python package manager; it never calls `sudo`, `apt`, `brew` or any
system service. If a step above genuinely fails, the script exits non-zero so the
failure is visible.

## Step 2 — verify the install

```sh
python3 -c 'import tatamifit; print(tatamifit.VERSION)'
python3 tatamifit.py --version
```

## Step 3 — plan a room

```sh
python3 tatamifit.py                       # interactive: type a width, a depth, Enter
printf '3.64\n2.73\n\n' | python3 tatamifit.py   # non-interactive
sh demo.sh                                 # three sessions end to end
```

If `install.sh` managed the editable install you can also just run:

```sh
tatamifit
```

## Step 4 — run the test suite

```sh
python3 -m pytest
```

The suite is a set of plain pytest functions and needs no network, no plugin and no
fixture files; every expected number is inline.

## Uninstall

Delete the checkout. Nothing was installed outside the Python environment, and the
planner never writes files.
