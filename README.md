# lns

`lns` finds symlinks below a directory, shows the absolute path stored by each link, and can remove selected links without touching their targets.
It is implemented as one self-contained Fish executable with no configuration or state files.

## Requirements

- macOS
- Fish
- `fd`
- The macOS `readlink`, `sort`, `seq`, and `rm` commands

## Usage

```text
lns [ROOT] [options]

Options
  -c, --contains STRING  only links whose target path contains STRING
  -b, --broken           only links that resolve to nothing
  -r, --remove           remove the listed links, after one confirmation
  -n, --dry-run          with --remove, list what would go and remove nothing
  -y, --yes              skip the confirmation prompt
  -a, --all              include dependency, cache and build trees
  -h, --help             show help
```

`ROOT` defaults to the current directory.
Links are reported but never followed, so a walk cannot descend into a target or loop through a link.
Relative targets are normalized against the link's parent without resolving the rest of a symlink chain.

`--contains` matches the target path rather than the link name.
`--broken` selects links whose targets do not exist, and the two filters can be combined.

Dependency, cache, and build trees such as `node_modules`, `.venv`, `dist`, `Library`, and `.git` are skipped by default.
Use `--all` to include them.
For compatibility with the original Fish function, `CLEAN_CLAUDE_EXCLUDES` adds directory names to the skip list.

`--remove` always lists candidates first and asks once before removing them.
Use `--dry-run` to stop after the listing or `--yes` to skip confirmation.
Only symlinks are removed, including broken links, and targets are never removed.

## Environment

- Non-empty `CLEAN_CLAUDE_EXCLUDES` adds directory names to the default skip list.
- Non-empty `NO_COLOR` disables color.
- Non-empty `FORCE_COLOR` enables color unless `NO_COLOR` is also non-empty.
- `HOME` is used to render paths below the home directory with `~`.

## Installation

A release consists of the checked-in `lns` executable.
For a manual installation, download the asset from the selected GitHub release, verify its published SHA-256 checksum, and install it on `PATH`:

```sh
install -d ~/.local/bin
install -m 0755 ./lns ~/.local/bin/lns
shasum -a 256 ~/.local/bin/lns
```

If migrating from the original autoloaded Fish function, remove it from the current shell or start a new one after installing the executable:

```fish
functions -e lns
```

## Development

The command has no build step and the test harness uses only Python's standard library.

```sh
make check
```

This runs the Fish syntax check, black-box tests, executable shape check, and isolated help smoke test.
The tests create and remove symlinks only below temporary directories.

## Release checklist

1. Run `make check`.
2. Run `make checksum` and record the SHA-256 digest.
3. Create the release tag from the reviewed commit.
4. Upload the checked-in `lns` file as the executable asset.
5. Download the remote asset and confirm its checksum matches the local file.
6. Update the dotfiles release label and checksum together.

Do not reuse or move a published tag.

## Rollback and uninstall

Rollback by restoring the previous release label and checksum in the installer, then applying the shell role again.
The command owns no user state, so rollback does not require a migration.

Uninstall by removing `~/.local/bin/lns` through the owning provisioner or manually:

```sh
rm ~/.local/bin/lns
```

## License

[MIT](LICENSE) Copyright (c) 2022 José Manuel Rosa Moncayo.
