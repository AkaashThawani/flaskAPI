import subprocess
import json
import sys
from config import ( # Import constants
    NSJAIL_PATH, NSJAIL_CFG, EXECUTOR_SCRIPT_PATH,
    SUBPROCESS_TIMEOUT, PYTHON_EXECUTABLE, LD_LIBRARY_PATH
)

def run_sandboxed_execution(user_script_path: str) -> subprocess.CompletedProcess:
    """
    Constructs and runs the nsjail command.
    """
    cmd = [
        NSJAIL_PATH,
        '--config', NSJAIL_CFG,
        '--quiet',
        '--env', f'LD_LIBRARY_PATH={LD_LIBRARY_PATH}',
        '--',
        PYTHON_EXECUTABLE,
        EXECUTOR_SCRIPT_PATH,
        user_script_path
    ]

    try:
        # Note: text=True (or encoding) is important for reading stdout/stderr
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            check=False # Handle non-zero exit codes manually
        )
        return process
    except FileNotFoundError:
        print(f"Error: nsjail executable not found at {NSJAIL_PATH}", file=sys.stderr)
        raise # Re-raise for the main handler
    except subprocess.TimeoutExpired:
        print("Script execution timed out (subprocess timeout).", file=sys.stderr)
        raise # Re-raise for the main handler
    except Exception as e:
        print(f"Error running subprocess: {e}", file=sys.stderr)
        raise # Re-raise for the main handler


def parse_execution_result(process: subprocess.CompletedProcess) -> tuple[dict, int]:
    """
    Parses the result from the CompletedProcess object returned by nsjail.
    """
    if process.stderr:
        print(f"nsjail stderr:\n{process.stderr.strip()}", file=sys.stderr)

    # Case 1: nsjail process failed
    if process.returncode != 0:
        error_detail = f"nsjail process exited with code {process.returncode}."
        try:
            output_data = json.loads(process.stdout)
            if output_data.get("error"):
                return {
                    "error": f"Script execution failed: {output_data['error']}",
                    "stdout": output_data.get("stdout", "")
                }, 400
        except (json.JSONDecodeError, TypeError):
            error_detail += f" nsjail stdout: {process.stdout or '[empty]'}"
        if process.stderr:
             error_detail += f" nsjail stderr: {process.stderr.strip()}"
        return {"error": "Execution failed inside sandbox.", "details": error_detail}, 500

    # Case 2: nsjail process succeeded - parse executor's output
    try:
        output_data = json.loads(process.stdout)
        if output_data.get("error"):
            return {
                "error": f"Script execution failed: {output_data['error']}",
                "stdout": output_data.get("stdout", "")
            }, 400
        else:
            return {
                "result": output_data.get("result"),
                "stdout": output_data.get("stdout", "")
            }, 200
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from successful nsjail execution stdout: {process.stdout}", file=sys.stderr)
        return {"error": "Failed to parse executor output.", "details": process.stdout}, 500