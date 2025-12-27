# Job Manager (Phase A Proposal)

Goal: survive browser refresh by persisting the *status* of long-running jobs,
without changing the execution model yet.

## Scope (Phase A)

- Persist job metadata for a small set of long-running tasks.
- Restore the last known job status after a browser refresh.
- No re-attach to running threads/processes (read-only status).

## Non-Goals (Phase A)

- Centralized scheduling or cancellation across all addons.
- Cross-process job control.
- Automatic resume or reattach to running tasks.

## Data Model (Proposed)

```
job_id: string
type: string            # "video_generation" | "keyframe_generation" | ...
status: string          # "queued" | "running" | "done" | "failed"
progress: number        # 0-100
message: string         # short status text
started_at: iso8601
updated_at: iso8601
metadata: dict          # e.g. project, storyboard, output path
```

## Persistence

- Store in JSON under project output:
  - `<ComfyUI>/output/<project>/jobs/_last_job.json`
  - Or per-job directory: `jobs/<job_id>.json`
- For non-project tasks, store under `~/.cindergrace/jobs/`.

## UI Behavior

- On page load, read the latest job file and display:
  - Status + last updated time
  - A hint: "Job may still be running in the backend. Check logs."
- If no job exists, hide the panel.

## Minimal Integration Points

1) Video Generator
   - On job start: write status `running`.
   - On completion/failure: update to `done`/`failed`.
2) Keyframe Generator
   - Same pattern.

## Future (Phase B)

- Central Job Manager service with:
  - Cancel/Retry
  - Unified job list in the UI
  - Log aggregation
