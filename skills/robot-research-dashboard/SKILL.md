---
name: robot-research-dashboard
description: Build and update a local HTML progress dashboard for long coding or research tasks, with task status, pending questions and defaults, recent outputs, blockers, and a live clock.
metadata:
  short-description: Track long tasks in a local HTML dashboard
---

# Robot Research Dashboard

Use this skill when a coding or research task is expected to take several steps or remain active long enough that a compact progress board would help. Create or maintain one standalone HTML file the user can open directly, with a compact dark navy layout inspired by the supplied reference images.

Show the task title and short summary, overall status, task checklist and progress, questions awaiting the user alongside the working default for each, recent outputs, blockers, and the current local time. Keep the information scannable and readable; tailor the layout to the current task instead of copying social media controls or decoration. Include an auto-refresh every 10 seconds so a page open in a browser picks up a newly rendered state file, and keep the on-page clock ticking between refreshes.

Keep a small JSON state file as the source of truth and regenerate the HTML with `scripts/render_dashboard.py`. The script accepts an input JSON file and an output HTML path. Use the schema in its help text and allow absent sections to render as empty states. Store dashboard files in a task-appropriate workspace location and tell the user where the HTML is saved. Keep generated output local; do not add global CLAUDE.md rules, persistent cross-task instructions, remote analytics, or external dependencies.

Update the state as meaningful task milestones occur, especially task status, changed assumptions/defaults, new outputs, and newly discovered or cleared blockers. Do not use the dashboard as a reason to interrupt the user: collect non-blocking questions with a clear default and continue independent work. For a decision that truly blocks progress, surface the question and pause only the dependent work.
