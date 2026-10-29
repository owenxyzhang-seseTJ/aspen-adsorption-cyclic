"""Run a PowerShell script on the Windows host through an existing SSH alias.

Aspen automation must execute in the logged-on interactive session, so this
only *launches* work (for example registers and starts a scheduled task); it
does not host Aspen itself.

Why the encoding dance: `powershell -EncodedCommand` does not accept a top-level
`param()` block, so the script body is wrapped in `& { ... }` and parameters are
appended after the closing brace.

Usage:
    python3 win_ps.py SCRIPT.ps1
    python3 win_ps.py run_adsim.ps1 --end-time 6000 --host my-win-box
"""
from pathlib import Path
import argparse
import base64
import os
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument("script", type=Path)
ap.add_argument("--host", default=os.environ.get("ADSIM_SSH_HOST", "windows-host"),
                help="SSH alias of the Windows host; set ADSIM_SSH_HOST or pass --host")
ap.add_argument("--end-time", type=float)
ap.add_argument("--extra", default="",
                help="additional PowerShell parameters appended verbatim")
ap.add_argument("--timeout", type=int, default=120)
args = ap.parse_args()

invocation = ""
if args.end_time is not None:
    invocation += f" -EndTime {args.end_time:g}"
invocation += args.extra

prefix = ("$ProgressPreference='SilentlyContinue'; "
          "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding;\n")
body = args.script.read_text(encoding="utf-8-sig")
source = prefix + "& {\n" + body + "\n}" + invocation
encoded = base64.b64encode(source.encode("utf-16le")).decode("ascii")
command = ("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe "
           "-NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded)

try:
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", args.host, command],
        capture_output=True, timeout=args.timeout)
except subprocess.TimeoutExpired as exc:
    print("SSH_TIMEOUT -- the remote command is still running, or the host is wedged")
    for stream in (exc.stdout, exc.stderr):
        if stream:
            print(stream.decode("utf-8", errors="replace"))
    raise SystemExit(124)

for stream in (result.stdout, result.stderr):
    try:
        print(stream.decode("utf-8-sig"))
    except UnicodeDecodeError:
        print(stream.decode("gb18030", errors="replace"))
print(f"SSH_EXIT_STATUS={result.returncode}")
raise SystemExit(result.returncode)
