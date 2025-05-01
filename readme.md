# Python Code Execution API

This project implements a secure API service using Flask that allows users to submit arbitrary Python scripts for execution on a server. The service utilizes `nsjail` for sandboxing to ensure safe execution. The result of the script's `main()` function and its standard output are returned to the user.

## Technology Stack

*   Python 3.10
*   Flask 
*   nsjail 
*   Docker
*   Google Cloud Run 
*   Google Artifact Registry

## Prerequisites

*   Docker Desktop installed and running.
*   `curl` (for Linux/macOS testing) or `Invoke-WebRequest` (for PowerShell testing).
*   Google Cloud SDK (`gcloud` CLI) installed and configured (for deployment).
*   A Google Cloud Project with Billing enabled and the following APIs activated:
    *   Cloud Run API (`run.googleapis.com`)
    *   Artifact Registry API (`artifactregistry.googleapis.com`)
    *   Cloud Build API (`cloudbuild.googleapis.com`)

## Setup & Local Execution

1.  **Clone the repository:**
    ```bash
    # Assuming you have put the code in a git repo
    # git clone <your-repo-url>
    # cd <repo-directory>
    ```

2.  **Build the Docker Image:**
    This builds the image, compiling `nsjail` and installing dependencies. Use a tag relevant to your project. Replace `<your-image-tag>` (e.g., `pyexec-api:latest` or the full registry path).
    ```bash
    docker build -t <your-image-tag> .
    ```
    *Example using registry path:*
    ```bash
    docker build -t us-east4-docker.pkg.dev/flaskapi-458517/flask-apis/basic-flask-api:v1.0 .
    ```

3.  **Run the Docker Container Locally:**
    This maps host port 8080 to the container's port 8080. Replace `<your-image-tag>` with the tag used in the build step.
    ```bash
    docker run -p 8080:8080 --rm <your-image-tag>
    ```
    *Example:*
    ```bash
    docker run -p 8080:8080 --rm us-east4-docker.pkg.dev/flaskapi-458517/flask-apis/basic-flask-api:v1.0
    ```

4.  **Local Testing Caveat:**
    *   The `nsjail` configuration used is optimized for the Google Cloud Run Gen2 environment.
    *   Due to restrictions in some local Docker Desktop/WSL2 environments, running the container locally *might* fail with errors like `clone(...) failed: Operation not permitted`.
    *   If local testing fails, ensure the `nsjail.cfg` used during the build has `clone_newnet: true` and that the `app.py` (or `sandbox.py`) does *not* include the `--disable_clone...` flags. However, the primary testing should be done against the deployed Cloud Run service.

5.  **Test Locally (if running successfully):**
    Open another terminal.

    *   **Using PowerShell (`Invoke-WebRequest`):**
        ```powershell
        Invoke-WebRequest -Uri http://localhost:8080/execute `
            -Method POST `
            -ContentType "application/json" `
            -Body '{
                      "script": "import pandas as pd\n\ndef main():\n    print(\"Local test run!\")\n    data = {\"col1\": [1, 2], \"col2\": [3, 4]}\n    df = pd.DataFrame(data=data)\n    return {\"shape\": df.shape, \"columns\": df.columns.tolist() }"
                    }' | ConvertFrom-Json
        ```

    *   **Using `curl` (Linux/macOS/Git Bash):**
        ```bash
        curl -X POST http://localhost:8080/execute \
             -H "Content-Type: application/json" \
             -d '{
                   "script": "import pandas as pd\n\ndef main():\n    print(\"Local test run!\")\n    data = {\"col1\": [1, 2], \"col2\": [3, 4]}\n    df = pd.DataFrame(data=data)\n    return {\"shape\": [df.shape[0], df.shape[1]], \"columns\": df.columns.tolist() }"
                 }' | jq # Optional: Pipe to jq for pretty printing
        ```

## Deployment to Google Cloud Run

1.  **Authenticate Docker with Artifact Registry:**
    Replace `<YOUR_REGION>` with your Artifact Registry region (e.g., `us-east4`).
    ```bash
    gcloud auth configure-docker <YOUR_REGION>-docker.pkg.dev
    ```
    *Example:*
    ```bash
    gcloud auth configure-docker us-east4-docker.pkg.dev
    ```

2.  **Push the Docker Image:**
    Ensure you have built and tagged the image with the full registry path (e.g., using the combined `docker build -t ... .` command). Replace `<YOUR_REGION>`, `<YOUR_PROJECT_ID>`, `<YOUR_REPO_NAME>`, `<IMAGE_NAME>`, `<TAG>` accordingly.
    ```bash
    docker push <YOUR_REGION>-docker.pkg.dev/<YOUR_PROJECT_ID>/<YOUR_REPO_NAME>/<IMAGE_NAME>:<TAG>
    ```
    *Example:*
    ```bash
    docker push us-east4-docker.pkg.dev/flaskapi-458517/flask-apis/basic-flask-api:v1.0
    ```

3.  **Deploy to Cloud Run:**
    Replace values as needed. **Crucially, includes `--execution-environment=gen2`**.
    ```bash
    gcloud run deploy <YOUR_SERVICE_NAME> \
        --image <YOUR_REGION>-docker.pkg.dev/<YOUR_PROJECT_ID>/<YOUR_REPO_NAME>/<IMAGE_NAME>:<TAG> \
        --region <YOUR_DEPLOY_REGION> \
        --platform managed \
        --port 8080 \
        --allow-unauthenticated \
        --execution-environment=gen2
    ```
    *Example:*
    ```bash
    gcloud run deploy my-first-api --image us-east4-docker.pkg.dev/flaskapi-458517/flask-apis/basic-flask-api:v1.0 --region us-east4 --platform managed --port 8080 --allow-unauthenticated --execution-environment=gen2
    ```
    Confirm deployment with `Y` when prompted. Note the `Service URL` provided.

## Testing Deployed Service Examples

The following examples assume the service has been deployed and is accessible at the URL:
`https://my-first-api-296354555904.us-east4.run.app` (Replace if yours is different).

Examples are provided for PowerShell (`Invoke-WebRequest`) and `curl` (Linux/macOS/Git Bash).

**1. Valid Script:**

*   **PowerShell:**
    ```powershell
    Invoke-WebRequest -Uri https://my-first-api-296354555904.us-east4.run.app/execute `
        -Method POST `
        -ContentType "application/json" `
        -Body '{
                  "script": "import numpy as np\nimport pandas as pd\n\ndef main():\n    print(\"Calculating...\")\n    s = pd.Series([1, 3, 5, np.nan, 6, 8])\n    print(f\"Series length: {len(s)}\")\n    # Convert numpy types for JSON\n    return {\"total\": float(s.sum()), \"count\": int(s.count()) }"
                }' | ConvertFrom-Json
    ```

*   **curl:**
    ```bash
    curl -X POST https://my-first-api-296354555904.us-east4.run.app/execute \
         -H "Content-Type: application/json" \
         -d '{
               "script": "import numpy as np\nimport pandas as pd\n\ndef main():\n    print(\"Calculating...\")\n    s = pd.Series([1, 3, 5, np.nan, 6, 8])\n    print(f\"Series length: {len(s)}\")\n    # Convert numpy types for JSON\n    return {\"total\": float(s.sum()), \"count\": int(s.count()) }"
             }' | jq # Optional: Pipe to jq for pretty printing
    ```
*Expected Output:* Successful response (200 OK) with `"result": {"total": 23.0, "count": 5}` and `"stdout": "Calculating...\nSeries length: 6\n"`.

**2. Script Without `main` Function:**

*   **PowerShell:**
    ```powershell
    Invoke-WebRequest -Uri https://my-first-api-296354555904.us-east4.run.app/execute `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"script": "print(\"This script has no main\")\nx = 1 + 1"}' | ConvertFrom-Json
    ```

*   **curl:**
    ```bash
    curl -X POST https://my-first-api-296354555904.us-east4.run.app/execute \
         -H "Content-Type: application/json" \
         -d '{"script": "print(\"This script has no main\")\nx = 1 + 1"}' | jq
    ```
*Expected Output:* Error response (400 Bad Request) with message like `"error": "...AttributeError: Script requires a callable 'main' function."` and `"stdout": "This script has no main\n"`.

**3. Script With Syntax Error:**

*   **PowerShell:**
    ```powershell
    Invoke-WebRequest -Uri https://my-first-api-296354555904.us-east4.run.app/execute `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"script": "def main():\n  print(\"Hello\")\n  x = 1 + \n  return {\"ok\": True}"}' | ConvertFrom-Json
    ```

*   **curl:**
    ```bash
    curl -X POST https://my-first-api-296354555904.us-east4.run.app/execute \
         -H "Content-Type: application/json" \
         -d '{"script": "def main():\n  print(\"Hello\")\n  x = 1 + \n  return {\"ok\": True}"}' | jq
    ```
*Expected Output:* Error response (400 Bad Request) with message like `"error": "...SyntaxError: invalid syntax..."` and `"stdout": ""`.

**4. Script Returning Non-JSON Serializable Type:**

*   **PowerShell:**
    ```powershell
    Invoke-WebRequest -Uri https://my-first-api-296354555904.us-east4.run.app/execute `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"script": "import numpy as np\ndef main():\n  print(\"Returning ndarray\")\n  # ndarray is not directly JSON serializable\n  return np.array([1,2,3])"}' | ConvertFrom-Json
    ```

*   **curl:**
    ```bash
    curl -X POST https://my-first-api-296354555904.us-east4.run.app/execute \
         -H "Content-Type: application/json" \
         -d '{"script": "import numpy as np\ndef main():\n  print(\"Returning ndarray\")\n  # ndarray is not directly JSON serializable\n  return np.array([1,2,3])"}' | jq
    ```
*Expected Output:* Error response (400 Bad Request) with message like `"error": "...TypeError: Return value of 'main' is not JSON serializable: Object of type ndarray is not JSON serializable"`, and `"stdout": "Returning ndarray\n"`.

**5. Script That Times Out:** (Timeout set to ~15 seconds)

*   **PowerShell:**
    ```powershell
    Invoke-WebRequest -Uri https://my-first-api-296354555904.us-east4.run.app/execute `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"script": "import time\ndef main():\n  print(\"Sleeping...\")\n  time.sleep(20)\n  print(\"Done sleeping\")\n  return {\"status\": \"finished\"}"}' | ConvertFrom-Json
    ```

*   **curl:**
    ```bash
    curl -X POST https://my-first-api-296354555904.us-east4.run.app/execute \
         -H "Content-Type: application/json" \
         -d '{"script": "import time\ndef main():\n  print(\"Sleeping...\")\n  time.sleep(20)\n  print(\"Done sleeping\")\n  return {\"status\": \"finished\"}"}' | jq
    ```
*Expected Output:* Error response (408 Request Timeout) with message like `"error": "Script execution timed out."`.

*   **Service URL:** `https://my-first-api-296354555904.us-east4.run.app`

*   **Using PowerShell (`Invoke-WebRequest`):**
    ```powershell
    Invoke-WebRequest -Uri https://my-first-api-296354555904.us-east4.run.app/execute `
        -Method POST `
        -ContentType "application/json" `
        -Body '{
                  "script": "import numpy as np\n\ndef main():\n    print(\"Hello from Cloud Run!\")\n    arr = np.array([1, 2, 3])\n    return {\"sum\": float(arr.sum()), \"mean\": float(arr.mean()) }"
                }' | ConvertFrom-Json
    ```

*   **Using `curl` (Linux/macOS/Git Bash):**
    ```bash
    curl -X POST https://my-first-api-296354555904.us-east4.run.app/execute \
         -H "Content-Type: application/json" \
         -d '{
               "script": "import numpy as np\n\ndef main():\n    print(\"Hello from Cloud Run!\")\n    arr = np.array([1, 2, 3])\n    return {\"sum\": float(arr.sum()), \"mean\": float(arr.mean()) }"
             }' | jq # Optional: Pipe to jq for pretty printing
    ```
    
    
## Available Libraries

User scripts executed via this API have access to:

*   Python 3.10 Standard Library (including `os`, `sys`, `json`, etc.)
*   `pandas`
*   `numpy`

## Security Considerations

*   Code execution is isolated using **nsjail**.
*   Resource limits (CPU time, memory, file size, process count) are enforced via `nsjail.cfg`.
*   Filesystem access is heavily restricted via read-only bind mounts defined in `nsjail.cfg`. Only `/tmp` is writable.
*   Network access for the executed script is disabled via network namespaces (`clone_newnet: true` in `nsjail.cfg`).
*   Process capabilities are dropped (`keep_caps: false` in `nsjail.cfg`).
*   User Namespaces are used locally but disabled on Cloud Run for compatibility. Process runs as container user (root) on Cloud Run.