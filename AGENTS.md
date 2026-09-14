# Repository instructions

## Purpose

`lns` is a standalone macOS command for finding symlinks below a directory, filtering them by target or broken state, and optionally removing only the listed links.
The checked-in `lns` executable is the release asset.

## Commands

```sh
make check
make test
make syntax
make smoke
make checksum
```

## Conventions

- Preserve the public `lns [ROOT] [--contains STRING] [--broken] [--remove] [--dry-run] [--yes] [--all]` interface.
- Keep runtime code in the single executable `lns` file.
- Prefix private application functions with `_lns_`, except for the privately bundled `_ui` helper family retained from the original.
- Use the bundled private output helpers for every styled line.
- Keep tests black-box and confine filesystem changes to temporary directories.
- Never follow symlinks while walking or remove their targets.
- Preserve `CLEAN_CLAUDE_EXCLUDES` as the compatibility environment variable for extending skipped directory names.
- Add no runtime or development dependency without explicit approval.
- Do not add a `--version` flag during the initial extraction.
- Release the reviewed executable itself without a generated build step.

## Runtime

The supported platform is macOS with Fish and `fd` installed.
The command also uses the macOS `readlink`, `sort`, `seq`, and `rm` commands.
It writes no configuration, cache, or state.

## Testing

Tests create real symlinks only inside temporary directories and must not inspect or mutate links elsewhere.
Every behavior change needs coverage at the public CLI boundary.
The complete suite and isolated executable smoke test are required before a release.

## Release

A release tag uses `v<major>.<minor>.<patch>` and publishes the checked-in `lns` file as the executable asset.
Do not reuse or move a published tag.
Record and verify the SHA-256 checksum of the exact asset before updating any installer.
