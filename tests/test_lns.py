import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LNS = Path(os.environ.get("LNS_UNDER_TEST", ROOT / "lns"))
FISH = shutil.which("fish")
CHARACTERIZING = os.environ.get("LNS_CHARACTERIZE") == "1"

HELP = """Usage: lns [ROOT] [options]

List every symlink under ROOT (default: the current directory) with the absolute
path it points at. Read-only unless --remove is given.

Options
  -c, --contains STRING  only links whose target path contains STRING
  -b, --broken           only links that resolve to nothing
  -r, --remove           remove the listed links, after one confirmation
  -n, --dry-run          with --remove, list what would go and remove nothing
  -y, --yes              skip the confirmation prompt
  -a, --all              include dependency, cache and build trees
  -h, --help             this text

--contains matches the target, not the link's own name, so
'lns --contains old-repo --remove' drops every link pointing into a repo you moved.
A link is reported and never followed, so the walk cannot descend into a target.
Broken links are flagged and are removable like any other; --broken lists only those,
so 'lns --broken --remove' sweeps the dead ones and 'lns -b -c old-repo' narrows to
the dead ones from one target. Unlike --contains, --broken asks about the link and
not its target, so an unreadable link counts as broken.
Dependency, cache and build trees (node_modules, .venv, dist, Library, ...) are
skipped unless --all: recursing them means hundreds of node_modules/.bin links.
The list comes from clean_claude, so CLEAN_CLAUDE_EXCLUDES extends it here too.
"""


class LnsCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name).resolve()
        self.workspace = self.home / "workspace"
        self.workspace.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def run_lns(self, *args, cwd=None, input_text=None, extra_env=None):
        env = {
            "HOME": str(self.home),
            "NO_COLOR": "1",
            "PATH": os.environ["PATH"],
            "TERM": "xterm-256color",
            "XDG_CONFIG_HOME": str(self.home / "config"),
        }
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [FISH, "--no-config", str(LNS), *map(str, args)],
            cwd=cwd or self.workspace,
            env=env,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def symlink(self, target, name, parent=None):
        link = (parent or self.workspace) / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        return link

    def install_failing_command(self, name):
        binary_directory = self.home / "bin"
        binary_directory.mkdir(exist_ok=True)
        command = binary_directory / name
        command.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        command.chmod(0o755)
        return binary_directory


class BasicCliTests(LnsCase):
    def test_help_matches_the_original_command(self):
        result = self.run_lns("--help")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, HELP)
        self.assertEqual(result.stderr, "")

    def test_unknown_option_uses_argparse_diagnostic(self):
        result = self.run_lns("--wat")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "lns: --wat: unknown option\n")

    def test_more_than_one_root_prints_help_and_fails(self):
        result = self.run_lns("one", "two")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, HELP)
        self.assertEqual(result.stderr, "")

    def test_missing_root_is_a_clear_error(self):
        missing = self.home / "missing"

        result = self.run_lns(missing)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "✗ Not a directory: ~/missing\n")

    def test_missing_fd_is_a_clear_error(self):
        result = self.run_lns(extra_env={"PATH": "/usr/bin:/bin"})

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "✗ lns needs fd (brew install fd).\n")

    def test_no_links_succeeds(self):
        result = self.run_lns()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "🤷 No symlinks under ~/workspace.\n")
        self.assertEqual(result.stderr, "")

    def test_no_color_overrides_forced_color_on_stderr(self):
        result = self.run_lns(
            self.home / "missing",
            extra_env={"FORCE_COLOR": "1", "NO_COLOR": "1"},
        )

        self.assertEqual(result.returncode, 1)
        self.assertNotIn("\x1b[", result.stderr)
        self.assertEqual(result.stderr, "✗ Not a directory: ~/missing\n")

    def test_force_color_adds_escapes_to_stdout(self):
        target = self.home / "target"
        target.mkdir()
        self.symlink(target, "link")

        result = self.run_lns(extra_env={"FORCE_COLOR": "1", "NO_COLOR": ""})

        self.assertEqual(result.returncode, 0)
        self.assertIn("\x1b[", result.stdout)
        self.assertIn("🔎 1 symlink under", result.stdout)
        self.assertEqual(result.stderr, "")


class DiscoveryAndFilteringTests(LnsCase):
    def setUp(self):
        super().setUp()
        self.targets = self.home / "targets"
        self.live_target = self.targets / "live"
        self.live_target.mkdir(parents=True)
        self.live_link = self.symlink("../targets/live", "live-link")
        self.broken_link = self.symlink("../targets/missing", "broken-link")

    def test_lists_sorted_links_with_one_hop_absolute_targets(self):
        result = self.run_lns()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            """🔎 2 symlinks under ~/workspace:
  · ~/workspace/broken-link → ~/targets/missing  ⚠ broken
  · ~/workspace/live-link → ~/targets/live
  Dependency and build trees were skipped; --all includes them.
✨ 2 symlinks.
""",
        )
        self.assertEqual(result.stderr, "")

    def test_reports_the_immediate_target_without_following_a_chain(self):
        intermediary = self.targets / "intermediary"
        intermediary.symlink_to("live")
        self.symlink("../targets/intermediary", "chain-link")

        result = self.run_lns("--contains", "intermediary")

        self.assertEqual(result.returncode, 0)
        self.assertIn("~/workspace/chain-link → ~/targets/intermediary\n", result.stdout)
        self.assertNotIn("chain-link → ~/targets/live", result.stdout)

    def test_contains_matches_targets_and_not_link_names(self):
        self.symlink("../other/place", "targets-in-name")

        result = self.run_lns("--contains", "targets")

        self.assertEqual(result.returncode, 0)
        self.assertIn("2 of 3 symlinks", result.stdout)
        self.assertIn("~/workspace/broken-link", result.stdout)
        self.assertIn("~/workspace/live-link", result.stdout)
        self.assertNotIn("~/workspace/targets-in-name →", result.stdout)

    def test_broken_and_contains_filters_compose(self):
        self.symlink("../archived/old-repo", "other-broken")

        result = self.run_lns("--broken", "--contains", "targets")

        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "🔎 1 of 3 symlinks under ~/workspace, broken and pointing at 'targets':\n",
            result.stdout,
        )
        self.assertIn("~/workspace/broken-link", result.stdout)
        self.assertNotIn("~/workspace/live-link →", result.stdout)
        self.assertNotIn("~/workspace/other-broken →", result.stdout)
        self.assertIn("✨ 1 broken symlink.\n", result.stdout)

    def test_no_filter_match_reports_the_unfiltered_count(self):
        result = self.run_lns("--contains", "nowhere")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            """🤷 No symlink under ~/workspace is pointing at 'nowhere'.
  2 found, none matching.
""",
        )

    def test_dependency_trees_are_skipped_unless_all_is_given(self):
        dependency = self.workspace / "node_modules" / "package"
        dependency.mkdir(parents=True)
        self.symlink("../../../targets/live", "binary", dependency)

        skipped = self.run_lns()
        included = self.run_lns("--all")

        self.assertEqual(skipped.returncode, 0)
        self.assertIn("🔎 2 symlinks under", skipped.stdout)
        self.assertNotIn("node_modules", skipped.stdout)
        self.assertEqual(included.returncode, 0)
        self.assertIn("🔎 3 symlinks under", included.stdout)
        self.assertIn("~/workspace/node_modules/package/binary", included.stdout)
        self.assertNotIn("Dependency and build trees were skipped", included.stdout)

    def test_clean_claude_excludes_extends_the_skipped_directories(self):
        generated = self.workspace / "generated"
        generated.mkdir()
        self.symlink("../../targets/live", "generated-link", generated)

        result = self.run_lns(extra_env={"CLEAN_CLAUDE_EXCLUDES": "generated"})

        self.assertEqual(result.returncode, 0)
        self.assertIn("🔎 2 symlinks under", result.stdout)
        self.assertNotIn("generated-link", result.stdout)

    def test_an_unreadable_broken_target_is_reported_but_cannot_match_contains(self):
        self.live_link.unlink()
        self.broken_link.rename(self.workspace / "unreadable")
        binary_directory = self.install_failing_command("readlink")
        path = f"{binary_directory}:{os.environ['PATH']}"

        listed = self.run_lns(extra_env={"PATH": path})
        filtered = self.run_lns("--contains", "targets", extra_env={"PATH": path})
        broken = self.run_lns("--broken", extra_env={"PATH": path})

        self.assertEqual(listed.returncode, 0)
        self.assertIn("~/workspace/unreadable → ⚠ unreadable\n", listed.stdout)
        self.assertEqual(filtered.returncode, 0)
        self.assertEqual(
            filtered.stdout,
            """🤷 No symlink under ~/workspace is pointing at 'targets'.
  1 found, none matching.
""",
        )
        self.assertEqual(broken.returncode, 0)
        self.assertIn("~/workspace/unreadable → ⚠ unreadable\n", broken.stdout)
        self.assertIn("✨ 1 broken symlink.\n", broken.stdout)


class RemovalTests(LnsCase):
    def setUp(self):
        super().setUp()
        self.target = self.home / "target"
        self.target.mkdir()
        self.link = self.symlink(self.target, "link")

    def test_dry_run_lists_without_prompting_or_removing(self):
        result = self.run_lns("--remove", "--dry-run")

        self.assertEqual(result.returncode, 0)
        self.assertIn("🧪 Dry run: nothing removed.\n", result.stdout)
        self.assertTrue(self.link.is_symlink())
        self.assertTrue(self.target.is_dir())

    def test_declined_confirmation_keeps_the_link(self):
        result = self.run_lns("--remove", input_text="n\n")

        self.assertEqual(result.returncode, 1)
        self.assertIn("⚠ Aborted.\n", result.stdout)
        self.assertTrue(self.link.is_symlink())
        self.assertTrue(self.target.is_dir())

    def test_yes_removes_live_and_broken_links_without_touching_targets(self):
        broken = self.symlink(self.home / "missing", "broken")

        result = self.run_lns("--remove", "--yes")

        self.assertEqual(result.returncode, 0)
        self.assertIn("✨ Removed 2 symlinks. Targets are untouched.\n", result.stdout)
        self.assertFalse(self.link.is_symlink())
        self.assertFalse(broken.is_symlink())
        self.assertTrue(self.target.is_dir())

    def test_failed_removal_reports_the_surviving_link(self):
        binary_directory = self.install_failing_command("rm")

        result = self.run_lns(
            "--remove",
            "--yes",
            extra_env={"PATH": f"{binary_directory}:{os.environ['PATH']}"},
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("⚠ Removed 0 of 1 symlink; the rest survived (permissions?).\n", result.stdout)
        self.assertTrue(self.link.is_symlink())
        self.assertTrue(self.target.is_dir())


@unittest.skipIf(CHARACTERIZING, "standalone checks do not apply to the source fixture")
class DistributionTests(LnsCase):
    def test_checked_in_command_is_the_self_contained_release_asset(self):
        source = LNS.read_text(encoding="utf-8")

        self.assertTrue(os.access(LNS, os.X_OK))
        self.assertTrue(source.startswith("#!/usr/bin/env fish\n"))
        self.assertNotIn("roles/shell", source)
        self.assertNotIn("source ", source)

    def test_copied_command_runs_without_the_repository(self):
        isolated = self.home / "isolated"
        isolated.mkdir()
        command = isolated / "lns"
        shutil.copy2(LNS, command)

        result = subprocess.run(
            [str(command), "--help"],
            cwd=isolated,
            env={
                "HOME": str(self.home),
                "NO_COLOR": "1",
                "PATH": os.environ["PATH"],
                "TERM": "xterm-256color",
                "XDG_CONFIG_HOME": str(self.home / "empty-config"),
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, HELP)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
