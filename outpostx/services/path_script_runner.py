"""
services/path_script_runner.py

Minimal v1 path script runner for OutpostX.

Purpose
-------
Executes a small line-oriented script used to navigate from an already-open
transport session to the target BBS before normal BBS login begins.

Supported commands
------------------
- Comment line:
    # any text

- TIMEOUT 5
    Sets the default timeout (seconds) used by subsequent WAITFOR commands.

- SEND "c KROCK"
    Sends a single line to the active adapter.

- WAITFOR OK "Help ?", "$" FAIL "*** RET", "*** DISCONNECTED"
    Waits until any declared success or failure pattern is seen.
    The first matching pattern wins.

Notes
-----
- This first-pass runner is transport-agnostic, but the initial integration
  target is TNC only.
- Patterns are treated as plain text in v1.
- The special token "###RET" is interpreted as a carriage return character.
- The runner logs each action through the supplied logger callback.
- Cancellation is honored through the supplied stop callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List
import csv
import io
import time
import re


class PathScriptError(Exception):
    """Base exception for path script failures."""


class PathScriptSyntaxError(PathScriptError):
    """Raised when a script line is malformed."""


class PathScriptTimeoutError(PathScriptError):
    """Raised when WAITFOR times out."""


class PathScriptAbortedError(PathScriptError):
    """Raised when script execution is canceled by the user."""

class PathScriptMatchError(PathScriptError):
    """Raised when WAITFOR matches an explicit FAIL pattern."""


@dataclass
class PathScriptContext:
    """
    Runtime dependencies used by the path script runner.

    Attributes
    ----------
    adapter:
        The active Send/Receive adapter. Must provide:
          - send_line(text: str)
          - drain_buffer() -> str   (optional but preferred)
          - expect_any(patterns, timeout=..., case_insensitive=..., regex=...)
            or a compatible equivalent

    log:
        Callback used for session logging.

    is_stop_requested:
        Callback returning True if the session has been canceled/aborted.
    """
    adapter: object
    log: Callable[[str], None]
    is_stop_requested: Callable[[], bool]


class PathScriptRunner:
    """
    Minimal v1 path script runner.

    Parameters
    ----------
    ctx:
        Runtime context containing the adapter and callbacks.

    default_timeout:
        Initial timeout, in seconds, used by WAITFOR before any TIMEOUT command.
    """

    def __init__(self, ctx: PathScriptContext, default_timeout: float = 10.0) -> None:
        self.ctx = ctx
        self.default_timeout = float(default_timeout)

    def run(self, script_text: str) -> None:
        """
        Execute the supplied path script.

        Parameters
        ----------
        script_text:
            Multiline path script text.

        Raises
        ------
        PathScriptSyntaxError
            If a command line is malformed.

        PathScriptTimeoutError
            If WAITFOR times out.

        PathScriptAbortedError
            If cancel/abort is requested.

        PathScriptError
            For other script execution errors.
        """
        timeout_seconds = self.default_timeout

        lines = script_text.splitlines()
        self.ctx.log("PathScript: starting")

        for line_number, raw_line in enumerate(lines, start=1):
            self._check_abort()

            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                self.ctx.log(f"PathScript[{line_number}]: comment")
                continue

            command, remainder = self._split_command(line, line_number)

            if command == "TIMEOUT":
                timeout_seconds = self._parse_timeout(remainder, line_number)
                self.ctx.log(
                    f"PathScript[{line_number}]: TIMEOUT {timeout_seconds:g} sec"
                )

            elif command == "SEND":
                text = self._parse_single_quoted_value(remainder, line_number, "SEND")
                self.ctx.log(f'PathScript[{line_number}]: SEND "{text}"')
                self.ctx.adapter.send_line(text)

            # 260421: Updated for new WAITFOR pattern
            elif command == "WAITFOR":
                ok_patterns, fail_patterns = self._parse_waitfor_groups(remainder, line_number)

                ok_display = ", ".join(f'"{p}"' for p in ok_patterns)
                fail_display = ", ".join(f'"{p}"' for p in fail_patterns)

                self.ctx.log(
                    f"PathScript[{line_number}]: WAITFOR OK {ok_display} "
                    f"FAIL {fail_display} (timeout={timeout_seconds:g}s)"
                )

                matched = self._waitfor_any(
                    ok_patterns=ok_patterns,
                    fail_patterns=fail_patterns,
                    timeout_seconds=timeout_seconds,
                    line_number=line_number,
                )

                group_name, matched_text = matched

                if group_name == "OK":
                    self.ctx.log(
                        f'PathScript[{line_number}]: WAITFOR matched OK "{matched_text}"'
                    )
                elif group_name == "FAIL":
                    self.ctx.log(
                        f'PathScript[{line_number}]: WAITFOR matched FAIL "{matched_text}"'
                    )
                    raise PathScriptMatchError(
                        f'Path script line {line_number}: WAITFOR matched FAIL pattern "{matched_text}".'
                    )
                else:
                    raise PathScriptError(
                        f"Path script line {line_number}: WAITFOR matched unexpected group {group_name!r}."
                    )

        self.ctx.log("PathScript: complete")

    def _split_command(self, line: str, line_number: int) -> tuple[str, str]:
        parts = line.split(None, 1)
        if not parts:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: empty command."
            )

        command = parts[0].upper()
        remainder = parts[1].strip() if len(parts) > 1 else ""
        return command, remainder


    def _parse_timeout(self, remainder: str, line_number: int) -> float:
        value = (remainder or "").strip()
        if not value:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: TIMEOUT requires a numeric value."
            )

        try:
            seconds = float(value)
        except ValueError as exc:
            raise PathScriptSyntaxError(
                f'Path script line {line_number}: TIMEOUT value "{value}" is not numeric.'
            ) from exc

        if seconds <= 0:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: TIMEOUT must be greater than zero."
            )

        return seconds


    def _parse_single_quoted_value(
        self,
        remainder: str,
        line_number: int,
        command_name: str,
    ) -> str:
        values = self._parse_csv_quoted_strings(remainder, line_number)
        if len(values) != 1:
            raise PathScriptSyntaxError(
                f'Path script line {line_number}: {command_name} requires exactly one quoted value.'
            )
        return self._decode_special_tokens(values[0])

    # 260421: Updated for new WAITFOR pattern
    def _parse_waitfor_groups(
        self,
        remainder: str,
        line_number: int,
    ) -> tuple[List[str], List[str]]:
        """
        Parse:

            WAITFOR OK "<success1>", "<success2>" FAIL "<fail1>", "<fail2>"

        Returns
        -------
        (ok_patterns, fail_patterns)
        """
        text = (remainder or "").strip()
        if not text:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: WAITFOR requires OK ... FAIL ... groups."
            )

        m = re.match(
            r"^OK\s+(?P<ok>.+?)\s+FAIL\s+(?P<fail>.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not m:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: WAITFOR syntax must be "
                f'OK "<success1>", ... FAIL "<fail1>", ...'
            )

        ok_text = (m.group("ok") or "").strip()
        fail_text = (m.group("fail") or "").strip()

        ok_values = self._parse_csv_quoted_strings(ok_text, line_number)
        fail_values = self._parse_csv_quoted_strings(fail_text, line_number)

        if not ok_values:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: WAITFOR requires at least one OK pattern."
            )
        if not fail_values:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: WAITFOR requires at least one FAIL pattern."
            )

        ok_patterns = [self._decode_special_tokens(v) for v in ok_values]
        fail_patterns = [self._decode_special_tokens(v) for v in fail_values]

        return ok_patterns, fail_patterns


    def _parse_csv_quoted_strings(self, text: str, line_number: int) -> List[str]:
        """
        Parse one or more CSV-style quoted strings.

        Example
        -------
        '"Help ?", "###RET"' -> ['Help ?', '###RET']
        """
        try:
            reader = csv.reader(
                io.StringIO(text),
                skipinitialspace=True,
            )
            values = next(reader, None)
        except Exception as exc:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: invalid quoted argument list."
            ) from exc

        if not values:
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: missing quoted argument(s)."
            )

        cleaned = [v.strip() for v in values]
        if any(v == "" for v in cleaned):
            raise PathScriptSyntaxError(
                f"Path script line {line_number}: empty quoted value is not allowed."
            )

        return cleaned

    def _decode_special_tokens(self, value: str) -> str:
        """
        Decode special script tokens.

        Supported in v1
        ----------------
        ###RET -> carriage return
        """
        return value.replace("###RET", "\r")


    def _waitfor_any(
        self,
        *,
        ok_patterns: Iterable[str],
        fail_patterns: Iterable[str],
        timeout_seconds: float,
        line_number: int,
    ) -> tuple[str, str]:
        """
        Wait until any supplied OK or FAIL plain-text pattern appears.

        Returns
        -------
        (group_name, matched_pattern)
            group_name is "OK" or "FAIL".
        """
        ok_patterns = list(ok_patterns)
        fail_patterns = list(fail_patterns)
        all_patterns = ok_patterns + fail_patterns

        expect_any = getattr(self.ctx.adapter, "expect_any", None)
        if callable(expect_any):
            try:
                result = expect_any(
                    all_patterns,
                    timeout=timeout_seconds,
                    case_insensitive=False,
                    regex=False,
                )
                if result:
                    if result in ok_patterns:
                        return ("OK", result)
                    if result in fail_patterns:
                        return ("FAIL", result)
                    raise PathScriptError(
                        f"Path script line {line_number}: WAITFOR matched unknown pattern {result!r}."
                    )
            except TypeError:
                pass
            except Exception as exc:
                raise PathScriptError(
                    f"Path script line {line_number}: WAITFOR failed."
                ) from exc

        deadline = time.monotonic() + timeout_seconds
        collected = ""

        while time.monotonic() < deadline:
            self._check_abort()

            try:
                chunk = self.ctx.adapter.drain_buffer()
            except Exception:
                chunk = ""

            if chunk:
                collected += chunk

                for pattern in ok_patterns:
                    if pattern in collected:
                        return ("OK", pattern)

                for pattern in fail_patterns:
                    if pattern in collected:
                        return ("FAIL", pattern)

            time.sleep(0.10)

        ok_joined = ", ".join(repr(p) for p in ok_patterns)
        fail_joined = ", ".join(repr(p) for p in fail_patterns)

        raise PathScriptTimeoutError(
            f"Path script line {line_number}: timeout waiting for "
            f"OK [{ok_joined}] or FAIL [{fail_joined}]."
        )

    def _check_abort(self) -> None:
        if self.ctx.is_stop_requested():
            raise PathScriptAbortedError("Path script aborted by user request.")    
        