#!/usr/bin/env python3
from __future__ import annotations

import argparse
import codecs
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REQUIRED_KEYS = ("library_id", "submission_zip", "workdir", "pytest_target")
HARNESS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = HARNESS_DIR / "results"


def _load_manifest(manifest_path: Path) -> dict:
    with manifest_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"Manifest missing required keys: {missing}")
    return data


def _extract_submission(zip_path: Path) -> Path:
    if not zip_path.exists():
        raise FileNotFoundError(f"Submission zip not found: {zip_path}")
    tmpdir = Path(tempfile.mkdtemp(prefix="audit_run_"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmpdir)
    nested = tmpdir / "pets_submission"
    if nested.is_dir():
        for item in nested.iterdir():
            shutil.move(str(item), str(tmpdir))
        nested.rmdir()
    return tmpdir


def _resolve_placeholders(value: str, submission_root: Path) -> str:
    return value.replace("{submission}", str(submission_root))


def _run_shell_command(command: str, cwd: Path, env: dict) -> None:
    subprocess.run(command, shell=True, cwd=cwd, env=env, check=True)


def _stream_pytest_pipe(
    pytest_cmd: list[str],
    cwd: Path,
    env: dict,
    log_fh,
) -> int:
    proc = subprocess.Popen(
        pytest_cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        log_fh.write(line)
        sys.stdout.write(line)
        sys.stdout.flush()
    proc.wait()
    return proc.returncode


def _stream_pytest_pty(
    pytest_cmd: list[str],
    cwd: Path,
    env: dict,
    log_fh,
) -> int:
    import pty

    master_fd, slave_fd = pty.openpty()
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            pytest_cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
    except Exception:
        os.close(master_fd)
        os.close(slave_fd)
        raise
    os.close(slave_fd)
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        while True:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    chunk = b""
                else:
                    raise
            if not chunk:
                text = decoder.decode(b"", final=True)
                if text:
                    log_fh.write(text)
                    sys.stdout.write(text)
                    sys.stdout.flush()
                break
            text = decoder.decode(chunk)
            if text:
                log_fh.write(text)
                sys.stdout.write(text)
                sys.stdout.flush()
    finally:
        os.close(master_fd)
        if proc is not None:
            proc.wait()
    return proc.returncode


def _stream_pytest_output(
    pytest_cmd: list[str],
    cwd: Path,
    env: dict,
    log_fh,
) -> int:
    if sys.platform == "win32":
        return _stream_pytest_pipe(pytest_cmd, cwd, env, log_fh)
    try:
        return _stream_pytest_pty(pytest_cmd, cwd, env, log_fh)
    except OSError:
        return _stream_pytest_pipe(pytest_cmd, cwd, env, log_fh)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--submission-root", default=None)
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parents[3]
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = workspace_root / manifest_path
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = _load_manifest(manifest_path)

    if args.submission_root:
        submission_root = Path(args.submission_root)
        if not submission_root.is_absolute():
            submission_root = workspace_root / submission_root
        nested = submission_root / "pets_submission"
        if (
            nested.is_dir()
            and not (
                submission_root / manifest["workdir"] / manifest["pytest_target"]
            ).exists()
        ):
            submission_root = nested
        results_stem = Path(manifest_path.name).stem
        return _run_manifest_with_root(
            manifest, submission_root, manifest_path.name, results_stem
        )
    return _run_manifest(manifest, workspace_root, manifest_path.name)


def _run_manifest_with_root(
    manifest: dict, submission_root: Path, manifest_name: str, stem: str
) -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    junit_xml = RESULTS_DIR / f"{stem}.xml"
    log_path = RESULTS_DIR / f"{stem}.log"

    t0 = time.monotonic()
    workdir = submission_root / manifest["workdir"]
    pytest_target = manifest["pytest_target"]
    pytest_args = manifest.get("pytest_args", [])
    pre_cmd = manifest.get("pre_cmd", [])
    env_overrides = manifest.get("env", {})

    if not workdir.exists():
        raise FileNotFoundError(f"workdir does not exist: {workdir}")

    env = os.environ.copy()
    for key, value in env_overrides.items():
        env[key] = _resolve_placeholders(str(value), submission_root)
    env.setdefault("RUN_DISTRIBUTIONAL_AUDIT", "0")

    for command in pre_cmd:
        _run_shell_command(command, workdir, env)

    pytest_cmd = [
        sys.executable,
        "-u",
        "-m",
        "pytest",
        pytest_target,
        f"--junitxml={junit_xml}",
        "--capture=tee-sys",
        "--tb=short",
        "-v",
        "-W",
        "ignore::DeprecationWarning",
        *pytest_args,
    ]
    pytest_env = env.copy()
    pytest_env["PYTHONUNBUFFERED"] = "1"

    print(f"  pytest {pytest_target} (workdir={workdir})", flush=True)
    with open(log_path, "w", encoding="utf-8") as log_fh:
        returncode = _stream_pytest_output(pytest_cmd, workdir, pytest_env, log_fh)
    elapsed = time.monotonic() - t0

    summary = {
        "manifest": manifest_name,
        "library_id": manifest["library_id"],
        "exit_code": returncode,
        "elapsed_s": round(elapsed, 2),
        "junit_xml": str(junit_xml),
        "log": str(log_path),
    }
    (RESULTS_DIR / f"{stem}.json").write_text(json.dumps(summary, indent=2))

    return returncode


def _run_manifest(manifest: dict, workspace_root: Path, manifest_name: str) -> int:
    zip_rel = manifest["submission_zip"]
    zip_path = HARNESS_DIR / zip_rel
    if not zip_path.is_absolute():
        zip_path = zip_path.resolve()

    submission_root = _extract_submission(zip_path)
    try:
        stem = Path(manifest_name).stem
        return _run_manifest_with_root(manifest, submission_root, manifest_name, stem)
    finally:
        shutil.rmtree(submission_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
