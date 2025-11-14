import subprocess
import json
import sys
import io
import contextlib
import importlib.util
import os
from config import ( # Import constants
    IS_DOCKER, NSJAIL_PATH, NSJAIL_CFG, EXECUTOR_SCRIPT_PATH,
    SUBPROCESS_TIMEOUT, PYTHON_EXECUTABLE, LD_LIBRARY_PATH
)

def run_sandboxed_execution(user_script_path: str):
    """
    Constructs and runs the nsjail command (Docker) or executes directly (local dev).
    """
    if IS_DOCKER:
        # Docker environment - use nsjail
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
    else:
        # Local development - run directly without sandboxing
        return run_local_execution(user_script_path)

def run_local_execution(user_script_path: str):
    """
    Runs Python code directly for local development (no sandboxing).
    This mimics the behavior of executor.py but runs locally.
    """
    stdout_capture = io.StringIO()
    result = None
    error = None
    exit_code = 0

    try:
        if not user_script_path or not os.path.exists(user_script_path):
            raise FileNotFoundError(f"Script file not found: {user_script_path}")

        with contextlib.redirect_stdout(stdout_capture):
            # Load the user script as a module
            spec = importlib.util.spec_from_file_location("user_script", user_script_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module spec: {user_script_path}")

            user_module = importlib.util.module_from_spec(spec)
            sys.modules["user_script"] = user_module
            spec.loader.exec_module(user_module)

            # Check for main() function - if it exists, call it (Function Mode)
            # If it doesn't exist, just execute the module (Script Mode)
            if hasattr(user_module, 'main') and callable(user_module.main):
                # Function Mode: Call main() and get return value
                returned_value = user_module.main()

                # Validate JSON serializability of the return value
                try:
                    json.dumps(returned_value)
                    result = returned_value # Store original object if serializable
                except TypeError as json_error:
                    raise TypeError(f"Return value of 'main' is not JSON serializable: {json_error}")
            else:
                # Script Mode: No main() function, just execute the module
                # No explicit return value for script mode
                result = None

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        error = f"{error_type}: {error_message}"
        exit_code = 1

    finally:
        # Output the results (or error) as a JSON object to stdout
        output_payload = {
            "result": result,
            "stdout": stdout_capture.getvalue(),
            "error": error
        }
        json_output = json.dumps(output_payload)

        # Create a mock CompletedProcess object
        class MockCompletedProcess:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        return MockCompletedProcess(json_output, "", exit_code)


def parse_execution_result(process) -> tuple[dict, int]:
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
