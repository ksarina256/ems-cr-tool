"""Subprocess helpers with structured results."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Mapping, Optional, Sequence


class CommandError(RuntimeError):
    """Raised when a command exits with a non-zero status."""

    def __init__(self, result: "CommandResult"):
        command = " ".join(result.args)
        message = (
            f"Command failed with exit code {result.returncode}: {command}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class CommandResult:
    args: Sequence[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner:
    """Executes commands and returns decoded output."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        check: bool = True,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                [str(arg) for arg in args],
                cwd=str(cwd) if cwd else None,
                env=dict(env) if env else None,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except FileNotFoundError as exc:
            result = CommandResult(
                args=[str(arg) for arg in args],
                returncode=127,
                stdout="",
                stderr=str(exc),
            )
            if check:
                raise CommandError(result) from exc
            return result
        result = CommandResult(
            args=[str(arg) for arg in args],
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and completed.returncode != 0:
            raise CommandError(result)
        return result
