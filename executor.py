import sys
import os
import importlib.util
import json
import io
import contextlib
import traceback

# Ensure necessary libraries are accessible inside the jail
try:
    import pandas
    import numpy
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

try:
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script file not found inside jail: {script_path}")

    with contextlib.redirect_stdout(stdout_capture):
        # Load the user script as a module
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module spec: {script_path}")

        user_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = user_module # Allow relative imports in user script
        spec.loader.exec_module(user_module)

        # Check for and call the main() function
        if not hasattr(user_module, 'main') or not callable(user_module.main):
            raise AttributeError("Script requires a callable 'main' function.")

        returned_value = user_module.main()

        # Validate JSON serializability of the return value
        try:
            json.dumps(returned_value)
            result = returned_value # Store original object if serializable
        except TypeError as json_error:
            raise TypeError(f"Return value of 'main' is not JSON serializable: {json_error}")

except Exception as e:
    error_type = type(e).__name__
    error_message = str(e)
    traceback.print_exc(file=sys.stderr) # Log full traceback to server logs
    error = f"{error_type}: {error_message}"
    exit_code = 1

finally:
    # Output the results (or error) as a JSON object to stdout
    output_payload = {
        "result": result,
        "stdout": stdout_capture.getvalue(),
        "error": error
    }
    print(json.dumps(output_payload))
    sys.exit(exit_code)