import argparse
import os
import pwd
import resource
import subprocess
import sys
import tempfile

def make_preexec(time_limit, mem_bytes, nofile, drop_priv):
    def _preexec():
        # CPU time (seconds)
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (time_limit, time_limit + 1))
        except Exception:
            pass
        # address space (virtual memory)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except Exception:
            pass
        # limit number of open files
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (nofile, nofile))
        except Exception:
            pass
        # put child in its own process group
        try:
            os.setpgrp()
        except Exception:
            pass
        # drop privileges to 'nobody' if possible
        if drop_priv:
            try:
                nobody = pwd.getpwnam("nobody")
                os.setgid(nobody.pw_gid)
                os.setuid(nobody.pw_uid)
            except Exception:
                pass
        # close extra fds
        try:
            maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            if maxfd == resource.RLIM_INFINITY:
                maxfd = 1024
        except Exception:
            maxfd = 1024
        for fd in range(3, int(maxfd)):
            try:
                os.close(fd)
            except OSError:
                pass
    return _preexec

def run_sandbox(target, target_args, time_limit, memory_mb, nofile, drop_priv):
    mem_bytes = memory_mb * 1024 * 1024
    preexec = make_preexec(time_limit, mem_bytes, nofile, drop_priv)

    # run in a temporary directory
    with tempfile.TemporaryDirectory(prefix="py_sandbox_") as td:
        env = {
            "PYTHONIOENCODING": "utf-8",
            # minimal PATH so the child can still find system python if needed
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        cmd = [sys.executable, "-S", os.path.abspath(target)] + target_args
        try:
            proc = subprocess.run(
                cmd,
                cwd=td,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=preexec,
                timeout=max(1, time_limit + 2),
                text=True,
            )
        except subprocess.TimeoutExpired as e:
            print(f"Sandbox: target timed out (>{time_limit}s)")
            return 124
        # print captured output
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        return proc.returncode

def main():
    parser = argparse.ArgumentParser(description="Run a Python script in a basic sandbox.")
    parser.add_argument("target", help="Path to target Python script")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the target script (prefix with -- if ambiguous)")
    parser.add_argument("--time", type=int, default=5, help="CPU time limit in seconds (default: 5)")
    parser.add_argument("--memory", type=int, default=128, help="Memory limit in MB (default: 128)")
    parser.add_argument("--nofile", type=int, default=64, help="Max open file descriptors (default: 64)")
    parser.add_argument("--drop-priv", action="store_true", help="Attempt to drop privileges to 'nobody' (only works if running as root)")
    args = parser.parse_args()

    if not os.path.exists(args.target):
        print("Target script not found:", args.target, file=sys.stderr)
        sys.exit(2)

    rc = run_sandbox(args.target, args.args, args.time, args.memory, args.nofile, args.drop_priv)
    sys.exit(rc)

if __name__ == "__main__":
    main()