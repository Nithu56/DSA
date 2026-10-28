"""Local Python backend for the DSA Event Scheduler. Uses only Python's standard library."""
from __future__ import annotations

import json
import threading
import webbrowser
from copy import deepcopy
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dsa import AVLIndex, DependencyGraph, FIFOQueue, PriorityQueue, UndoStack, intervals_overlap, merge_sort

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "scheduler_data.json"
HOST, PORT = "127.0.0.1", 8765
ACTIVE_STATUSES = {"scheduled", "in progress"}
ALL_STATUSES = {"scheduled", "in progress", "completed", "cancelled"}


def showcase_events() -> list[dict]:
    return [
        {"id": 1, "title": "Algorithms lecture", "description": "AVL rotations and heaps", "start_time": "2026-11-02T09:00", "end_time": "2026-11-02T10:00", "priority": 3, "status": "scheduled", "resource": "Lecture Hall A"},
        {"id": 2, "title": "Project review", "description": "Milestone demo and team feedback", "start_time": "2026-11-02T10:00", "end_time": "2026-11-02T10:45", "priority": 5, "status": "scheduled", "resource": "Lecture Hall A"},
        {"id": 3, "title": "Graph workshop", "description": "Hands-on BFS and DFS practice", "start_time": "2026-11-02T11:00", "end_time": "2026-11-02T12:00", "priority": 2, "status": "scheduled", "resource": "Innovation Lab"},
        {"id": 4, "title": "Industry networking", "description": "Connect with alumni and local technology teams", "start_time": "2026-11-02T13:00", "end_time": "2026-11-02T14:00", "priority": 4, "status": "scheduled", "resource": "Atrium"},
        {"id": 5, "title": "Design sprint", "description": "Prototype review with the student product team", "start_time": "2026-11-02T14:30", "end_time": "2026-11-02T16:00", "priority": 1, "status": "in progress", "resource": "Innovation Lab"},
    ]


def parse_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Time must be text in ISO date/time format.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed


class Scheduler:
    """Owns event state and runs all DSA operations in Python."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.events: list[dict] = []
        self.dependencies: list[tuple[int, int]] = []
        self.waiting = FIFOQueue()
        self.history = UndoStack()
        self._load()

    def _load(self) -> None:
        try:
            saved = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(saved.get("events"), list) and isinstance(saved.get("dependencies"), list):
                self.events = saved["events"]
                self.dependencies = [tuple(edge) for edge in saved["dependencies"]]
                self.waiting = FIFOQueue(saved.get("waiting", []))
                for snapshot in saved.get("history", []):
                    self.history.push(snapshot)
                return
        except (OSError, ValueError, TypeError):
            pass
        self._set_showcase()
        self._persist()

    def _set_showcase(self) -> None:
        self.events = showcase_events()
        self.dependencies = [(1, 2), (1, 3), (3, 4)]
        self.waiting = FIFOQueue([{"id": 2, "title": "Project review", "resource": "Lecture Hall A"}])

    def _persist(self) -> None:
        payload = {
            "events": self.events,
            "dependencies": self.dependencies,
            "waiting": self.waiting.items,
            "history": self.history._items[-25:],
        }
        temp = DATA_FILE.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(DATA_FILE)

    def _snapshot(self) -> dict:
        return {"events": deepcopy(self.events), "dependencies": deepcopy(self.dependencies)}

    def _record(self) -> None:
        self.history.push(self._snapshot())
        if len(self.history) > 25:
            self.history._items.pop(0)

    @staticmethod
    def _active(event: dict) -> bool:
        return event.get("status") in ACTIVE_STATUSES

    def _conflicts(self, candidate: dict, exclude_id: int | None = None) -> list[str]:
        resource = str(candidate.get("resource", "")).strip().casefold()
        if not resource or not self._active(candidate):
            return []
        conflicts = []
        for event in self.events:
            if event["id"] == exclude_id or not self._active(event):
                continue
            if str(event.get("resource", "")).strip().casefold() != resource:
                continue
            if intervals_overlap(candidate["start_time"], candidate["end_time"], event["start_time"], event["end_time"]):
                conflicts.append(event["title"])
        return conflicts

    def save_event(self, data: dict) -> str:
        title = str(data.get("title", "")).strip()
        description = str(data.get("description", "")).strip()
        resource = str(data.get("resource", "")).strip()
        start = str(data.get("start_time", ""))
        end = str(data.get("end_time", ""))
        status = str(data.get("status", "scheduled"))
        try:
            priority_float = float(data.get("priority", 0))
        except (TypeError, ValueError):
            raise ValueError("Priority must be a whole number from -5 to 5.")
        if not title:
            raise ValueError("Enter an event title.")
        if len(title) > 120 or len(description) > 2000 or len(resource) > 100:
            raise ValueError("One or more fields exceed the allowed length.")
        if not start or not end:
            raise ValueError("Choose a start and end time.")
        try:
            start_dt, end_dt = parse_time(start), parse_time(end)
        except ValueError:
            raise ValueError("Choose valid start and end times.")
        if end_dt <= start_dt:
            raise ValueError("End time must be later than start time.")
        if not priority_float.is_integer() or not -5 <= priority_float <= 5:
            raise ValueError("Priority must be a whole number from -5 to 5.")
        if status not in ALL_STATUSES:
            raise ValueError("Choose a valid event status.")
        event_id = data.get("id")
        event_id = int(event_id) if event_id not in (None, "") else None
        if event_id is not None and not any(event["id"] == event_id for event in self.events):
            raise ValueError("This event no longer exists. Refresh the page and try again.")
        event = {"id": event_id or max((item["id"] for item in self.events), default=0) + 1,
                 "title": title, "description": description, "start_time": start, "end_time": end,
                 "priority": int(priority_float), "status": status, "resource": resource}
        conflicts = self._conflicts(event, event_id)
        if conflicts:
            raise ValueError("Resource conflict with " + ", ".join(conflicts) + ". Change the time or resource.")
        self._record()
        if event_id:
            self.events = [event if item["id"] == event_id else item for item in self.events]
            message = "Event updated successfully."
        else:
            self.events.append(event)
            message = "Event created successfully."
        self._persist()
        return message

    def delete_event(self, event_id: int) -> str:
        event = next((item for item in self.events if item["id"] == event_id), None)
        if event is None:
            raise ValueError("That event no longer exists.")
        self._record()
        self.events = [item for item in self.events if item["id"] != event_id]
        self.dependencies = [edge for edge in self.dependencies if event_id not in edge]
        self.waiting = FIFOQueue(request for request in self.waiting.items if request["id"] != event_id)
        self._persist()
        return "Event deleted. Use Undo to restore it."

    def undo(self) -> str:
        snapshot = self.history.pop()
        if snapshot is None:
            raise ValueError("There is no event or dependency change to undo.")
        self.events = snapshot["events"]
        self.dependencies = [tuple(edge) for edge in snapshot["dependencies"]]
        self._persist()
        return "Last event or dependency change was undone."

    def queue_action(self, action: str, event_id: int | None = None) -> str:
        if action == "clear":
            self.waiting = FIFOQueue()
            self._persist()
            return "Waiting queue cleared."
        if action == "add":
            event = next((item for item in self.events if item["id"] == event_id), None)
            if event is None:
                raise ValueError("Create an event before adding a queue request.")
            if any(request["id"] == event_id for request in self.waiting.items):
                raise ValueError("That event is already in the waiting queue.")
            self.waiting.enqueue({"id": event["id"], "title": event["title"], "resource": event.get("resource", "")})
            self._persist()
            return "Request added to the saved FIFO queue."
        if action == "process":
            requests = self.waiting.items
            valid_requests = []
            removed_stale = False
            for request in requests:
                event = next((item for item in self.events if item["id"] == request["id"]), None)
                if event is None or not self._active(event):
                    removed_stale = True
                    continue
                valid_requests.append(request)
            if removed_stale:
                self.waiting = FIFOQueue(valid_requests)
            for index, request in enumerate(self.waiting.items):
                event = next((item for item in self.events if item["id"] == request["id"]), None)
                if event is None:
                    continue
                if self._conflicts(event, event["id"]):
                    continue
                self.waiting.remove_at(index)
                self._persist()
                return f"Processed next eligible request: {event['title']}."
            if removed_stale:
                self._persist()
            raise ValueError("No eligible request is available; blocked requests remain queued." if len(self.waiting) else "The waiting queue is empty.")
        raise ValueError("Unknown queue action.")

    def add_dependency(self, before: int, after: int) -> str:
        known_ids = {event["id"] for event in self.events}
        if before not in known_ids or after not in known_ids:
            raise ValueError("Choose two existing events for a dependency.")
        graph = self.graph()
        if any(a == before and b == after for a, b in self.dependencies):
            raise ValueError("That dependency already exists.")
        if not graph.add_dependency(before, after):
            raise ValueError("An event cannot depend on itself, and dependencies cannot create a cycle.")
        self._record()
        self.dependencies = graph.edges()
        self._persist()
        return "Dependency added successfully."

    def graph(self) -> DependencyGraph:
        graph = DependencyGraph(self.dependencies)
        for event in self.events:
            graph.add_node(event["id"])
        return graph

    def view(self, query: dict) -> dict:
        events = list(self.events)
        prefix = query.get("prefix", "").strip()
        if prefix:
            index = AVLIndex()
            for event in events:
                index.insert(event["title"], event["id"])
            matching_ids = set(index.search_prefix(prefix))
            events = [event for event in events if event["id"] in matching_ids]
        status = query.get("status", "all")
        if status in ALL_STATUSES:
            events = [event for event in events if event["status"] == status]
        sort = query.get("sort", "start")
        keys = {
            "start": lambda event: (event["start_time"], event["id"]),
            "title": lambda event: (event["title"].casefold(), event["id"]),
            "priority": lambda event: (-event["priority"], event["start_time"], event["id"]),
        }
        events = merge_sort(events, key=keys.get(sort, keys["start"]))
        heap = PriorityQueue(event for event in self.events if self._active(event))
        graph = self.graph()
        try:
            start_id = int(query.get("start", ""))
        except ValueError:
            start_id = 0
        if start_id not in {event["id"] for event in self.events}:
            start_id = self.events[0]["id"] if self.events else 0
        title_by_id = {event["id"]: event["title"] for event in self.events}
        return {
            "events": events,
            "counts": {value: sum(event["status"] == value for event in self.events) for value in ("scheduled", "in progress", "completed", "cancelled")},
            "priority": heap.ordered(),
            "waiting": self.waiting.items,
            "dependencies": [list(edge) for edge in self.dependencies],
            "history_length": len(self.history),
            "graph": {"start": start_id, "nodes": self.events,
                      "edges": [[a, b] for a, b in graph.edges()],
                      "bfs": [title_by_id[event_id] for event_id in graph.bfs(start_id)],
                      "dfs": [title_by_id[event_id] for event_id in graph.dfs(start_id)]},
        }

    def showcase(self) -> str:
        self._record()
        self._set_showcase()
        self._persist()
        return "Showcase schedule loaded."

    def import_data(self, payload: dict) -> str:
        events = payload.get("events")
        dependencies = payload.get("dependencies")
        if not isinstance(events, list) or not isinstance(dependencies, list):
            raise ValueError("This file is not a valid event scheduler backup.")
        ids: set[int] = set()
        clean_events = []
        for raw in events:
            if not isinstance(raw, dict):
                raise ValueError("The backup contains an invalid event.")
            event = dict(raw)
            try:
                event["id"] = int(event["id"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Every imported event needs a numeric ID.")
            if event["id"] in ids:
                raise ValueError("The backup contains duplicate event IDs.")
            ids.add(event["id"])
            event["priority"] = event.get("priority", 0)
            event.setdefault("description", "")
            event.setdefault("resource", "")
            event.setdefault("status", "scheduled")
            self.save_event_validation(event)
            clean_events.append(event)
        candidate_graph = DependencyGraph()
        for event_id in ids:
            candidate_graph.add_node(event_id)
        normalized_edges = []
        for edge in dependencies:
            if not isinstance(edge, list) or len(edge) != 2:
                raise ValueError("The backup contains an invalid dependency.")
            try:
                before, after = int(edge[0]), int(edge[1])
            except (TypeError, ValueError):
                raise ValueError("The backup contains an invalid dependency ID.")
            if before not in ids or after not in ids:
                raise ValueError("The backup contains a dependency with a missing event.")
            if not candidate_graph.add_dependency(before, after):
                raise ValueError("The backup contains a duplicate or cyclic dependency.")
            normalized_edges.append((before, after))
        self._record()
        self.events = clean_events
        self.dependencies = normalized_edges
        self.waiting = FIFOQueue()
        self._persist()
        return "Backup imported successfully."

    @staticmethod
    def save_event_validation(event: dict) -> None:
        title = str(event.get("title", "")).strip()
        if not title or len(title) > 120 or len(str(event.get("description", ""))) > 2000 or len(str(event.get("resource", ""))) > 100:
            raise ValueError("The backup contains an invalid event title or field length.")
        if event.get("status") not in ALL_STATUSES:
            raise ValueError(f"Invalid status for “{title}”.")
        try:
            if not -5 <= int(event["priority"]) <= 5 or int(event["priority"]) != float(event["priority"]):
                raise ValueError
            if parse_time(event["end_time"]) <= parse_time(event["start_time"]):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Invalid time or priority for “{title}”.")


SCHEDULER = Scheduler()


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "EventScheduler/1.0"

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2_000_000:
            raise ValueError("Request is too large.")
        raw = self.rfile.read(length)
        return json.loads(raw or b"{}")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/api/state":
            with SCHEDULER.lock:
                self._json(200, SCHEDULER.view({key: values[0] for key, values in parse_qs(url.query).items()}))
            return
        if url.path == "/api/export":
            with SCHEDULER.lock:
                self._json(200, {"format": "dsa-event-scheduler", "version": 1,
                                 "events": SCHEDULER.events,
                                 "dependencies": [list(edge) for edge in SCHEDULER.dependencies]})
            return
        path = "/index.html" if url.path == "/" else url.path
        target = (BASE_DIR / path.lstrip("/")).resolve()
        if target.parent != BASE_DIR or target.name not in {"index.html", "style.css", "app.js"}:
            self.send_error(404)
            return
        try:
            content = target.read_bytes()
        except OSError:
            self.send_error(404)
            return
        content_type = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}.get(target.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        try:
            payload = self._body()
            with SCHEDULER.lock:
                if self.path == "/api/events":
                    message = SCHEDULER.save_event(payload)
                elif self.path == "/api/delete":
                    message = SCHEDULER.delete_event(int(payload.get("id", 0)))
                elif self.path == "/api/undo":
                    message = SCHEDULER.undo()
                elif self.path == "/api/queue":
                    message = SCHEDULER.queue_action(str(payload.get("action", "")), int(payload["id"]) if payload.get("id") else None)
                elif self.path == "/api/dependencies":
                    message = SCHEDULER.add_dependency(int(payload.get("before", 0)), int(payload.get("after", 0)))
                elif self.path == "/api/showcase":
                    message = SCHEDULER.showcase()
                elif self.path == "/api/import":
                    message = SCHEDULER.import_data(payload)
                else:
                    self._json(404, {"error": "Unknown API operation."})
                    return
            self._json(200, {"message": message})
        except ValueError as error:
            self._json(400, {"error": str(error)})
        except Exception as error:
            self._json(500, {"error": f"Could not complete the request: {error}"})


def main() -> None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    except OSError as error:
        print(f"Could not start the scheduler at http://{HOST}:{PORT}: {error}")
        input("Press Enter to close this window...")
        return
    print(f"Event Scheduler is running at http://{HOST}:{PORT}")
    print("Keep this window open while using the app. Press Ctrl+C to stop it.")
    webbrowser.open(f"http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Event Scheduler...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
