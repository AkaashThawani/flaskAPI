import sys
import os
import importlib.util
import json
import io
import contextlib
import traceback
import base64
import time
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
import gc

# Ensure necessary libraries are accessible inside the jail
try:
    # Configure matplotlib for headless operation (no GUI/display)
    import os
    os.environ['MPLBACKEND'] = 'Agg'  # Use non-interactive backend
    os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'  # Use writable temp directory

    # Import matplotlib and set backend
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # Core Data Science
    import pandas
    import numpy
    import scipy
    import seaborn
    import plotly

    # Data Manipulation
    import openpyxl
    import xlrd
    import requests

    # Image Processing
    import PIL

    # Web Scraping
    import bs4
    import lxml

    # Utilities
    import dateutil
    import pytz
    import tqdm

except ImportError as ie:
    print(json.dumps({
        "result": None,
        "stdout": "",
        "error": f"ImportError inside jail: {ie}. Check nsjail.cfg mounts."
    }), file=sys.stdout)
    sys.exit(1)

# Get user script path from command line argument
script_path = sys.argv[1]
script_dir = os.path.dirname(script_path)
module_name = os.path.splitext(os.path.basename(script_path))[0]

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

try:
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script file not found inside jail: {script_path}")

    # Read the script to count lines and analyze imports
    with open(script_path, 'r') as f:
        script_content = f.read()
        performance_metrics["code_lines"] = len(script_content.split('\n'))

    # Track initial memory (if psutil available)
    gc.collect()  # Clean up before measurement
    if PSUTIL_AVAILABLE:
        performance_metrics["memory_start"] = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    else:
        performance_metrics["memory_start"] = 0

    # Start timing
    start_time = time.perf_counter()
    start_cpu = time.process_time()

    with contextlib.redirect_stdout(stdout_capture):
        # Load the user script as a module
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module spec: {script_path}")

        user_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = user_module # Allow relative imports in user script
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
            # No explicit return value for script mode
            result = None

        # Capture any matplotlib plots that were created
        visualizations = capture_matplotlib_plots()

    # End timing
    end_time = time.perf_counter()
    end_cpu = time.process_time()

    # Calculate performance metrics
    performance_metrics["execution_time"] = end_time - start_time
    performance_metrics["cpu_time"] = end_cpu - start_cpu
    if PSUTIL_AVAILABLE:
        performance_metrics["memory_peak"] = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        print(f"DEBUG: Memory peak calculated: {performance_metrics['memory_peak']:.2f} MB", file=sys.stderr)
    else:
        performance_metrics["memory_peak"] = 0
        print("DEBUG: psutil not available, memory set to 0", file=sys.stderr)

    # Analyze libraries used (simple regex approach)
    import_lines = [line.strip() for line in script_content.split('\n') if line.strip().startswith('import ') or line.strip().startswith('from ')]
    performance_metrics["libraries_used"] = import_lines

    # Calculate output size
    stdout_content = stdout_capture.getvalue()
    performance_metrics["output_size"] = len(stdout_content.encode('utf-8')) + len(json.dumps(result).encode('utf-8'))

    # Add debug info to the performance metrics
    performance_metrics["debug_info"] = {
        "psutil_available": PSUTIL_AVAILABLE,
        "script_lines": len(script_content.split('\n')),
        "import_lines_found": len(import_lines)
    }

except Exception as e:
    error_type = type(e).__name__
    error_message = str(e)
    traceback.print_exc(file=sys.stderr) # Log full traceback to server logs
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
    print(json.dumps(output_payload))
    sys.exit(exit_code)
