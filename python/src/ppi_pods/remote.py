"""SSH/SCP execution for the pods runtime."""

from __future__ import annotations

import asyncio
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class SSHResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class RemoteExecutor(Protocol):
    async def exec(self, command: str, timeout: int | None = None) -> SSHResult: ...

    async def exec_stream(
        self,
        command: str,
        timeout: int | None = None,
        force_tty: bool = False,
    ) -> int: ...

    async def scp_file(self, local_path: str, remote_path: str) -> bool: ...

    def get_workspace_path(self, host_path: str) -> str: ...


@dataclass(slots=True)
class SubprocessSSHExecutor:
    ssh_cmd: str

    async def exec(self, command: str, timeout: int | None = None) -> SSHResult:
        ssh_args, host = self._split_ssh_cmd(self.ssh_cmd)
        proc = await asyncio.create_subprocess_exec(
            *ssh_args,
            host,
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return SSHResult(
            exit_code=proc.returncode or 0,
            stdout=(stdout or b"").decode(),
            stderr=(stderr or b"").decode(),
        )

    async def exec_stream(self, command: str, timeout: int | None = None, force_tty: bool = False) -> int:
        ssh_args, host = self._split_ssh_cmd(self.ssh_cmd)
        proc = await asyncio.create_subprocess_exec(
            *ssh_args,
            host,
            command,
            stdin=None if force_tty else asyncio.subprocess.PIPE,
            stdout=None if force_tty else asyncio.subprocess.PIPE,
            stderr=None if force_tty else asyncio.subprocess.PIPE,
        )
        try:
            if force_tty:
                return await asyncio.wait_for(proc.wait(), timeout=timeout)

            assert proc.stdout is not None
            assert proc.stderr is not None
            while True:
                stdout_line = await proc.stdout.readline()
                stderr_line = await proc.stderr.readline()
                if stdout_line:
                    print(stdout_line.decode(), end="")
                if stderr_line:
                    print(stderr_line.decode(), end="", file=sys.stderr)
                if not stdout_line and not stderr_line and proc.returncode is not None:
                    break
                if proc.returncode is None and proc.stdout.at_eof() and proc.stderr.at_eof():
                    break
            return await asyncio.wait_for(proc.wait(), timeout=timeout)
        finally:
            if proc.returncode is None:
                proc.kill()

    async def scp_file(self, local_path: str, remote_path: str) -> bool:
        ssh_args, host = self._split_ssh_cmd(self.ssh_cmd)
        scp_args = self._build_scp_args(ssh_args, host, local_path, remote_path)
        proc = await asyncio.create_subprocess_exec(
            *scp_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    def get_workspace_path(self, host_path: str) -> str:
        return str(Path(host_path).as_posix())

    def _split_ssh_cmd(self, ssh_cmd: str) -> tuple[list[str], str]:
        parts = shlex.split(ssh_cmd)
        if not parts:
            raise ValueError("ssh_cmd cannot be empty")
        if parts[0] != "ssh":
            raise ValueError("ssh_cmd must start with 'ssh'")

        ssh_args = [parts[0]]
        host = ""
        login_user: str | None = None
        i = 1
        while i < len(parts):
            part = parts[i]
            if part.startswith("-"):
                ssh_args.append(part)
                if part in {"-p", "-i", "-o", "-J"} and i + 1 < len(parts):
                    ssh_args.append(parts[i + 1])
                    i += 1
                elif part == "-l" and i + 1 < len(parts):
                    login_user = parts[i + 1]
                    i += 1
            else:
                host = part
                break
            i += 1

        if not host:
            raise ValueError("ssh_cmd must include a host")
        if login_user and "@" not in host:
            host = f"{login_user}@{host}"
        return ssh_args, host

    def _build_scp_args(self, ssh_args: list[str], host: str, local_path: str, remote_path: str) -> list[str]:
        scp_args = ["scp"]
        i = 1
        while i < len(ssh_args):
            part = ssh_args[i]
            if part == "-p" and i + 1 < len(ssh_args):
                scp_args.extend(["-P", ssh_args[i + 1]])
                i += 2
                continue
            if part == "-l" and i + 1 < len(ssh_args):
                i += 2
                continue
            if part in {"-i", "-o", "-J"} and i + 1 < len(ssh_args):
                scp_args.extend([part, ssh_args[i + 1]])
                i += 2
                continue
            scp_args.append(part)
            i += 1
        scp_args.extend([local_path, f"{host}:{remote_path}"])
        return scp_args
