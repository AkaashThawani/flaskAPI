
import os
import subprocess 
import tempfile
import json
import sys
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import helpers and config
from config import *
from sandbox import run_sandboxed_execution, parse_execution_result

app = Flask(__name__)
CORS(app)
# --- Flask Routes ---

@app.route('/', methods=['GET'])
def health_check():
    """Endpoint to check service status."""
    return jsonify({"status": "ok"}), 200

@app.route('/execute', methods=['POST'])
def execute_script():
    """Check validation and then executes code."""
    # 1. Input Validation
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    data = request.get_json()
    if not data or 'script' not in data:
        return jsonify({"error": "Missing 'script' key in JSON body"}), 400
    user_script_content = data.get('script')
    if not isinstance(user_script_content, str) or not user_script_content.strip():
        return jsonify({"error": "'script' must be a non-empty string"}), 400

    user_script_file_path = None
    try:
        # 2. Create Temporary User Script File
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f_user:
            user_script_file_path = f_user.name
            f_user.write(user_script_content)

        # 3. Run Sandboxed Execution
        process = run_sandboxed_execution(user_script_file_path)

        # 4. Parse Results
        response_data, status_code = parse_execution_result(process)
        return jsonify(response_data), status_code

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Script execution timed out."}), 408
    except Exception as e:
        # Catch unexpected errors during setup or helper calls
        print(f"Internal server error in /execute route: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    finally:
        # 5. Cleanup Temporary User Script File
        if user_script_file_path and os.path.exists(user_script_file_path):
            try:
                os.unlink(user_script_file_path)
            except OSError as e_unlink:
                print(f"Error deleting temp file {user_script_file_path}: {e_unlink}", file=sys.stderr)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)