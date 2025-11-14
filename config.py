import os

# Detect if we're running in Docker or locally
IS_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'

if IS_DOCKER:
    # Docker environment (Linux)
    NSJAIL_PATH = '/usr/local/bin/nsjail'
    NSJAIL_CFG = 'nsjail.cfg'
    EXECUTOR_SCRIPT_PATH = '/app/executor.py'
    PYTHON_EXECUTABLE = '/usr/local/bin/python'
    LD_LIBRARY_PATH = '/usr/local/lib:/usr/lib:/lib'
else:
    # Local development environment (Windows)
    # For local dev, we'll skip sandboxing and run directly
    NSJAIL_PATH = None  # Will be handled differently
    NSJAIL_CFG = None
    EXECUTOR_SCRIPT_PATH = None
    PYTHON_EXECUTABLE = 'python'  # Use system python
    LD_LIBRARY_PATH = ''

SUBPROCESS_TIMEOUT = 15
