# Security Design

CodeForge AI must never give a local language model unrestricted operating-system access.

## Initial policy

Low-risk tools:
- read_file
- list_files
- search_code
- find_references
- git_status
- git_diff

Approval-required tools:
- apply_patch
- create_file
- delete_file

Blocked initially:
- arbitrary shell execution
- git push
- destructive system commands

## Workspace boundary

Repository tools should operate only inside an explicitly selected repository root.

Future versions will add stronger path validation and sandboxed command execution.

## Known limitation: full-file rewrite reliability (Phase 4)

`app/agent/service.py` asks the model to return the complete new content of
a file rather than a diff or patch — a deliberate choice, since asking a
small local model to hand-write a correct unified diff is less
reliable than a full rewrite. In practice, for small, explicit,
single-function requests ("add a docstring, change nothing else"), the
model has been observed to:

- Regenerate the entire file and drop unrelated functions/classes
  entirely (observed: a request to add one docstring returned a file with
  every other function deleted)
- Echo fragments of its own prompt instructions back as if they were file
  content (observed: a literal `--- NEW CONTENT OF ... ---` line inserted
  as the first line of a Python file, which would have been a syntax
  error)

Both were caught in manual review before being applied — this is
precisely the failure mode the approval gate (`/agent/{id}/apply` requiring
an explicit user click after reviewing the diff) exists to catch. No
patch is ever applied without a human seeing the actual diff first.

This is a known, real limitation of small local models at this task, not
a bug — worth trying a coder-tuned or larger model if this becomes a
priority, or moving the agent from full-file-rewrite to a targeted
patch/splice strategy. Documented here rather than hidden because
understanding a system's failure modes is part of understanding the
system.