import subprocess
import json
import sys
import io
import contextlib
import importlib.util
import os
import base64
from config import ( # Import constants
    IS_DOCKER, NSJAIL_PATH, NSJAIL_CFG, EXECUTOR_SCRIPT_PATH,
    SUBPROCESS_TIMEOUT, PYTHON_EXECUTABLE, LD_LIBRARY_PATH
)

# Set matplotlib backend globally before any imports
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

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
    Enhanced to capture data visualizations and special output types.
    """
    import time
    import gc
    try:
        import psutil
        PSUTIL_AVAILABLE = True
    except ImportError:
        psutil = None
        PSUTIL_AVAILABLE = False

    stdout_capture = io.StringIO()
    result = None
    error = None
    exit_code = 0
    visualizations = []

    # Performance monitoring
    performance_metrics = {
        "execution_time": 0,
        "cpu_time": 0,
        "memory_peak": 0,
        "memory_start": 0,
        "libraries_used": [],
        "code_lines": 0,
        "output_size": 0
    }

    try:
        if not user_script_path or not os.path.exists(user_script_path):
            raise FileNotFoundError(f"Script file not found: {user_script_path}")

        # Read the script to count lines and analyze imports
        with open(user_script_path, 'r') as f:
            script_content = f.read()
            performance_metrics["code_lines"] = len(script_content.split('\n'))

        # Track initial memory (if psutil available)
        gc.collect()  # Clean up before measurement
        if PSUTIL_AVAILABLE and psutil is not None:
            performance_metrics["memory_start"] = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        else:
            performance_metrics["memory_start"] = 0

        # Start timing
        start_time = time.perf_counter()
        start_cpu = time.process_time()

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

                # Process the return value for special types
                result = process_return_value(returned_value)
            else:
                # Script Mode: No main() function, just execute the module
                # Check for any visualizations created during execution
                result = None

            # Capture any matplotlib plots that were created
            visualizations = capture_matplotlib_plots()

        # End timing
        end_time = time.perf_counter()
        end_cpu = time.process_time()

        # Calculate performance metrics
        performance_metrics["execution_time"] = end_time - start_time
        performance_metrics["cpu_time"] = end_cpu - start_cpu
        if PSUTIL_AVAILABLE and psutil is not None:
            performance_metrics["memory_peak"] = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        else:
            performance_metrics["memory_peak"] = 0

        # Analyze libraries used (simple regex approach)
        import_lines = [line.strip() for line in script_content.split('\n') if line.strip().startswith('import ') or line.strip().startswith('from ')]
        performance_metrics["libraries_used"] = import_lines

        # Calculate output size
        stdout_content = stdout_capture.getvalue()
        performance_metrics["output_size"] = len(stdout_content.encode('utf-8')) + len(json.dumps(result).encode('utf-8'))

    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        error = f"{error_type}: {error_message}"
        exit_code = 1

    finally:
        # Clear any remaining plots to avoid memory issues
        plt.close('all')

        # Output the results (or error) as a JSON object to stdout
        output_payload = {
            "result": result,
            "stdout": stdout_capture.getvalue(),
            "error": error,
            "visualizations": visualizations,
            "performance": performance_metrics
        }
        json_output = json.dumps(output_payload)

        # Create a mock CompletedProcess object
        class MockCompletedProcess:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        return MockCompletedProcess(json_output, "", exit_code)


def process_return_value(value):
    """
    Process return values to handle special types like pandas DataFrames.
    """
    if value is None:
        return None

    # Check if it's a pandas DataFrame
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            return {
                "_type": "dataframe",
                "data": value.to_dict('records'),
                "columns": value.columns.tolist(),
                "index": value.index.tolist(),
                "shape": value.shape,
                "dtypes": {col: str(dtype) for col, dtype in value.dtypes.items()}
            }
    except ImportError:
        pass

    # Check if it's a pandas Series
    try:
        import pandas as pd
        if isinstance(value, pd.Series):
            return {
                "_type": "series",
                "data": value.to_dict(),
                "name": value.name,
                "dtype": str(value.dtype),
                "index": list(value.index)
            }
    except ImportError:
        pass

    # Check if it's a PIL Image
    try:
        from PIL import Image
        if isinstance(value, Image.Image):
            # Convert PIL image to base64
            buffer = io.BytesIO()
            # Save in PNG format for web compatibility
            value.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return {
                "_type": "image",
                "format": "png",
                "data": f"data:image/png;base64,{img_base64}",
                "size": value.size,
                "mode": value.mode
            }
    except ImportError:
        pass

    # Try to serialize normally
    try:
        json.dumps(value)
        return value
    except TypeError:
        # If not serializable, convert to string representation
        return {
            "_type": "unserializable",
            "value": str(value),
            "type": type(value).__name__
        }


def capture_matplotlib_plots():
    """
    Capture any matplotlib plots that were created and return them as base64 images.
    """
    visualizations = []

    try:
        # Get all current figures
        figures = plt.get_fignums()

        for fig_num in figures:
            fig = plt.figure(fig_num)

            # Save figure to base64
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            visualizations.append({
                "type": "matplotlib",
                "format": "png",
                "data": f"data:image/png;base64,{img_base64}",
                "figure_number": fig_num
            })

    except Exception as e:
        print(f"Warning: Failed to capture matplotlib plots: {e}", file=sys.stderr)

    return visualizations


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
                "stdout": output_data.get("stdout", ""),
                "visualizations": output_data.get("visualizations", [])
            }, 400
        else:
            return {
                "result": output_data.get("result"),
                "stdout": output_data.get("stdout", ""),
                "visualizations": output_data.get("visualizations", []),
                "performance": output_data.get("performance", {})
            }, 200
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from successful nsjail execution stdout: {process.stdout}", file=sys.stderr)
        return {"error": "Failed to parse executor output.", "details": process.stdout}, 500
