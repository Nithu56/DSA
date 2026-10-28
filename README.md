# Real-Time Event Scheduling System

A Python-backed event scheduling app and DSA microproject. The browser provides the interface; the Python app runs the scheduling rules, data structures, and algorithms.

## Run the app

1. Install Python 3 and Git for Windows if needed.
2. Double-click `run_windows.bat`.
3. The app opens in your browser at `http://127.0.0.1:8765/`.
4. Keep the server window open while you use the app. Press Ctrl+C in that window to stop it.

The Python server uses only the standard library—no Flask or package installation. Events, dependencies, waiting requests, and undo history are saved to `scheduler_data.json` in the project folder.

## What you can demonstrate

- Create, edit, delete, search, filter, and sort events.
- Save only valid time ranges and detect overlapping events that share a room.
- See the active events ranked by priority and add/process FIFO waiting requests.
- Add event prerequisites, view their arrows, and run BFS or DFS. Self-links and cycles are rejected.
- Undo event and dependency changes.
- Export/import events and dependency links as JSON. Queue requests and undo history remain in the local data file and aren’t part of the exported backup.
- Load a five-event showcase schedule.

## How the DSA features work

| Feature | Python structure/algorithm | Purpose |
|---|---|---|
| Title-prefix search | AVL tree | Find event titles while keeping the search tree balanced |
| Schedule ordering | Merge sort | Sort by start time, title, or priority |
| Priority ranking | Binary max-heap | Show higher-priority active events first |
| Waiting requests | FIFO queue | Keep requests in arrival order and process eligible ones |
| Undo | Stack | Restore the previous event/dependency state |
| Prerequisites | Directed graph, cycle check, BFS, DFS | Store event links, reject impossible cycles, explore reachable events |
| Room availability | Interval overlap check | Find same-room events whose times overlap |

An arrow **A → B** means event A is a prerequisite for event B. The interface is JavaScript, but it only displays the page and sends user actions to Python; the DSA operations themselves are in `dsa.py` and `server.py`.

## Run the Python tests

Open PowerShell in this folder and run:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

To print a small example of the DSA operations, run `python dsa.py` or double-click `run_python_demo.bat`.

## Push to GitHub the easy way

1. Create a **new empty repository** on GitHub. Don’t add a README there—the project already contains one.
2. Double-click `push_to_github.bat` in this folder.
3. Enter a commit message (or press Enter to use the suggested one).
4. Paste the repository’s HTTPS URL, for example `https://github.com/your-name/event-scheduler.git`.
5. Complete GitHub sign-in if it prompts you.

The helper initializes Git if needed, commits the project files, and pushes the `main` branch. `.gitignore` keeps the local schedule file, old database/log files, and Python cache out of GitHub. The synced `sources/` reference folder and local `AGENTS.md` are not included.

This is a local classroom demo, not a shared multi-user service or a hard real-time scheduler.
