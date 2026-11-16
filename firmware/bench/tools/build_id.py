# PlatformIO pre-script: the firmware prints its own source identity
# (`build` command, and on every WAKE line), so a bench record names the build
# it came from. `git describe`, with -dirty when the tree has local changes.
Import("env")  # noqa: F821
import subprocess

try:
    ident = subprocess.check_output(
        ["git", "describe", "--always", "--dirty", "--abbrev=12"],
        cwd=env["PROJECT_DIR"], text=True).strip()  # noqa: F821
except Exception:
    ident = "unknown"
env.Append(CPPDEFINES=[("FW_BUILD_ID", env.StringifyMacro(ident))])  # noqa: F821
