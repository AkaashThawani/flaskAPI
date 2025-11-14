
import os
import subprocess
import tempfile
import json
import sys
import traceback
import pkg_resources
import base64
import io
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

@app.route('/libraries', methods=['GET'])
def get_libraries():
    """Endpoint to get information about available libraries."""
    try:
        # Get all installed packages
        installed_packages = {}
        for dist in pkg_resources.working_set:
            installed_packages[dist.project_name.lower()] = {
                "name": dist.project_name,
                "version": dist.version,
                "summary": getattr(dist, 'summary', ''),
                "homepage": getattr(dist, 'homepage', ''),
            }

        # Define library categories with common import statements and examples
        library_categories = {
            "data_science": {
                "title": "Data Science & Analysis",
                "libraries": {
                    "pandas": {
                        "import": "import pandas as pd",
                        "example": "df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})\nprint(df.head())",
                        "description": "Powerful data manipulation and analysis library"
                    },
                    "numpy": {
                        "import": "import numpy as np",
                        "example": "arr = np.array([1, 2, 3, 4, 5])\nprint(f'Mean: {arr.mean()}')",
                        "description": "Fundamental package for array computing"
                    },
                    "scipy": {
                        "import": "import scipy",
                        "example": "from scipy import stats\nresult = stats.ttest_1samp([1, 2, 3, 4, 5], 3)\nprint(result)",
                        "description": "Scientific computing and technical computing"
                    },
                    "matplotlib": {
                        "import": "import matplotlib.pyplot as plt",
                        "example": "plt.plot([1, 2, 3], [1, 4, 2])\nplt.show()",
                        "description": "Comprehensive library for creating static plots"
                    },
                    "seaborn": {
                        "import": "import seaborn as sns",
                        "example": "import pandas as pd\nsns.lineplot(data=pd.DataFrame({'x': [1,2,3], 'y': [1,4,2]}), x='x', y='y')",
                        "description": "Statistical data visualization based on matplotlib"
                    },
                    "plotly": {
                        "import": "import plotly.express as px",
                        "example": "fig = px.line(x=[1, 2, 3], y=[1, 4, 2])\nfig.show()",
                        "description": "Interactive graphing library for Python"
                    },
                    "scikit-learn": {
                        "import": "from sklearn.linear_model import LinearRegression",
                        "example": "model = LinearRegression()\nmodel.fit([[1], [2], [3]], [1, 4, 2])",
                        "description": "Machine learning library for Python"
                    },
                    "statsmodels": {
                        "import": "import statsmodels.api as sm",
                        "example": "import numpy as np\nX = np.random.randn(100)\nmodel = sm.OLS(X, sm.add_constant(np.arange(100))).fit()",
                        "description": "Statistical models and tests"
                    },
                    "sympy": {
                        "import": "import sympy as sp",
                        "example": "x = sp.Symbol('x')\nprint(sp.integrate(x**2, x))",
                        "description": "Computer algebra system written in pure Python"
                    }
                }
            },
            "machine_learning": {
                "title": "Machine Learning & AI",
                "libraries": {
                    "tensorflow": {
                        "import": "import tensorflow as tf",
                        "example": "model = tf.keras.Sequential([tf.keras.layers.Dense(1)])\nprint('TensorFlow ready')",
                        "description": "Open source machine learning framework"
                    },
                    "torch": {
                        "import": "import torch",
                        "example": "x = torch.tensor([1, 2, 3])\nprint(x)",
                        "description": "Tensors and dynamic neural networks in Python"
                    },
                    "transformers": {
                        "import": "from transformers import pipeline",
                        "example": "classifier = pipeline('sentiment-analysis')\nprint(classifier('I love this!'))",
                        "description": "State-of-the-art machine learning for NLP"
                    }
                }
            },
            "data_io": {
                "title": "Data I/O & Databases",
                "libraries": {
                    "openpyxl": {
                        "import": "import openpyxl",
                        "example": "wb = openpyxl.Workbook()\nws = wb.active\nws['A1'] = 'Hello'\nprint('Excel file created')",
                        "description": "Library to read/write Excel 2010 xlsx/xlsm files"
                    },
                    "sqlalchemy": {
                        "import": "from sqlalchemy import create_engine",
                        "example": "engine = create_engine('sqlite:///:memory:')\nprint('Database engine created')",
                        "description": "SQL toolkit and Object-Relational Mapping"
                    },
                    "requests": {
                        "import": "import requests",
                        "example": "response = requests.get('https://httpbin.org/get')\nprint(response.json())",
                        "description": "Python HTTP library for humans"
                    }
                }
            },
            "image_processing": {
                "title": "Image Processing",
                "libraries": {
                    "pillow": {
                        "import": "from PIL import Image",
                        "example": "img = Image.new('RGB', (100, 100), color='red')\nprint(f'Size: {img.size}')",
                        "description": "Python Imaging Library (PIL) fork"
                    },
                    "opencv-python": {
                        "import": "import cv2",
                        "example": "import numpy as np\nimg = np.zeros((100, 100, 3), dtype=np.uint8)\nprint('OpenCV image created')",
                        "description": "Open source computer vision library"
                    }
                }
            },
            "nlp": {
                "title": "Natural Language Processing",
                "libraries": {
                    "nltk": {
                        "import": "import nltk",
                        "example": "from nltk.tokenize import word_tokenize\nwords = word_tokenize('Hello world!')\nprint(words)",
                        "description": "Natural Language Toolkit for Python"
                    },
                    "spacy": {
                        "import": "import spacy",
                        "example": "nlp = spacy.load('en_core_web_sm')\ndoc = nlp('Hello world!')\nprint([token.text for token in doc])",
                        "description": "Industrial-strength Natural Language Processing"
                    }
                }
            },
            "web_scraping": {
                "title": "Web Scraping",
                "libraries": {
                    "beautifulsoup4": {
                        "import": "from bs4 import BeautifulSoup",
                        "example": "soup = BeautifulSoup('<html><body>Hello</body></html>', 'html.parser')\nprint(soup.body.text)",
                        "description": "Library for pulling data out of HTML and XML files"
                    },
                    "selenium": {
                        "import": "from selenium import webdriver",
                        "example": "# Requires webdriver\ndriver = webdriver.Chrome()\nprint('Selenium ready')",
                        "description": "Browser automation and testing"
                    }
                }
            },
            "utilities": {
                "title": "Utilities & Development",
                "libraries": {
                    "tqdm": {
                        "import": "from tqdm import tqdm",
                        "example": "for i in tqdm(range(100)):\n    pass\nprint('Progress bar complete')",
                        "description": "Fast, extensible progress bar for Python"
                    },
                    "jupyter": {
                        "import": "import jupyter",
                        "example": "print('Jupyter environment available')",
                        "description": "Interactive computing and data science"
                    },
                    "pytest": {
                        "import": "import pytest",
                        "example": "def test_example():\n    assert 1 + 1 == 2\nprint('Testing framework ready')",
                        "description": "Framework for writing and running tests"
                    }
                }
            }
        }

        # Build response with installed packages and metadata
        response = {
            "categories": library_categories,
            "installed_packages": installed_packages,
            "total_libraries": len(installed_packages)
        }

        return jsonify(response), 200

    except Exception as e:
        print(f"Error getting libraries: {e}", file=sys.stderr)
        return jsonify({"error": f"Failed to get library information: {str(e)}"}), 500

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
    app.run(host='0.0.0.0', port=5000, debug=False)
