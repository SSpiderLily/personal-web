"""Single-threaded controlling-TTY probe for the admin bootstrap integration test."""
import os
import pty
import select
import signal
import sys
import time

password = sys.stdin.buffer.read()
pid, master = pty.fork()
if pid == 0:
    os.execv(sys.executable, [sys.executable, '-m', 'app.admin_init'])
transcript = bytearray()
prompts = (b'Username: ', b'Password (12', b'Repeat password: ')
replies = (b'tty-owner\n', password + b'\n', password + b'\n')
sent = 0
exit_status = None
try:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        readable, _, _ = select.select([master], [], [], 0.2)
        if readable:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            transcript.extend(chunk)
            if sent < len(prompts) and prompts[sent] in transcript:
                os.write(master, replies[sent])
                sent += 1
        completed, status = os.waitpid(pid, os.WNOHANG)
        if completed:
            exit_status = status
            break
finally:
    os.close(master)
    if exit_status is None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _, exit_status = os.waitpid(pid, 0)

safe_output = bytes(transcript).replace(password, b'[redacted]').decode(errors='replace')
if sent != len(prompts) or os.waitstatus_to_exitcode(exit_status) != 0:
    print(f'PTY bootstrap failed after {sent} prompts: {safe_output}', file=sys.stderr)
    raise SystemExit(1)
if password in transcript:
    print('PTY bootstrap echoed the password.', file=sys.stderr)
    raise SystemExit(1)
