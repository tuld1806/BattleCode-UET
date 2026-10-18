import subprocess
import sys

_original_run = subprocess.run

def _patched_run(*args, **kwargs):
    # If capture_output is True and stdin is not set, explicitly set stdin to DEVNULL
    # This avoids inheriting an invalid handle on Windows environments where std handles are closed.
    if kwargs.get('capture_output') and kwargs.get('stdin') is None:
        kwargs['stdin'] = subprocess.DEVNULL
    return _original_run(*args, **kwargs)

subprocess.run = _patched_run
