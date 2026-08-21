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
