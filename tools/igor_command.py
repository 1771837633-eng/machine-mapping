"""Send an Igor command through the documented /X interface of an existing instance.

An exit code of zero means dispatch only, never verified processing completion.
No /I or /N is used: no new instance or forced experiment close.
"""
import argparse
import subprocess
from pathlib import Path


def dispatch(executable, command):
    executable = Path(executable).resolve()
    if executable.name.lower() != 'igor64.exe' or not executable.is_file():
        raise ValueError('Select the installed Igor64.exe')
    if len(command.encode('utf-8')) > 2400 or any(c in command for c in '\r\n\0'):
        raise ValueError('Command must be a single bounded Igor command line')
    if not running_instance():
        raise ValueError('Open exactly one Igor64 instance before dispatch')
    # Igor 9 parses the raw /X tail itself, rather than using Windows argv rules.
    # subprocess.list2cmdline adds literal backslashes before embedded quotes.
    # The executable is quoted normally; Igor gets the command's quotes verbatim.
    command_line = subprocess.list2cmdline([str(executable)]) + ' /X "' + command + '"'
    subprocess.run(command_line, executable=str(executable), check=True, timeout=20)
    return {'status': 'dispatched_unverified', 'command': command}


def running_instance():
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
         '$instances=@(Get-Process -Name Igor64 -ErrorAction SilentlyContinue); if($instances.Count -eq 1 -and $instances[0].Responding){"ready"}else{"not_ready"}'],
        capture_output=True, text=True, check=True, timeout=10,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.stdout.strip() == 'ready'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe', required=True)
    p.add_argument('--file', type=Path, help='UTF-8 file containing one Igor command')
    p.add_argument('command', nargs='?')
    args = p.parse_args()
    command = args.file.read_text(encoding='utf-8').strip() if args.file else args.command
    if not command:
        p.error('Specify a command or --file')
    print(dispatch(args.exe, command))
