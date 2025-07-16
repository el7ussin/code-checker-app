import os
import json
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/analyze', methods=['POST'])
def analyze_code():
    files = request.get_json()
    if not files:
        return jsonify({"error": "No files provided"}), 400

    # Save files temporarily
    for file_info in files:
        file_path = os.path.join(UPLOAD_FOLDER, file_info['fileName'])
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_info['content'])
    
    # --- Run Pylint ---
    try:
        pylint_process = subprocess.run(
            ['pylint', UPLOAD_FOLDER, '--output-format=json'],
            capture_output=True, text=True, check=False
        )
        pylint_results = json.loads(pylint_process.stdout) if pylint_process.stdout else []
    except json.JSONDecodeError:
        pylint_results = [{"message": "Pylint analysis failed to produce valid JSON.", "type": "fatal"}]

    # --- Run Bandit (Security) ---
    try:
        bandit_process = subprocess.run(
            ['bandit', '-r', UPLOAD_FOLDER, '-f', 'json'],
            capture_output=True, text=True, check=False
        )
        bandit_results = json.loads(bandit_process.stdout) if bandit_process.stdout else {"results": []}
    except json.JSONDecodeError:
        bandit_results = {"results": [{"issue_text": "Bandit analysis failed to produce valid JSON."}]}

    # --- Run Radon (Complexity) ---
    try:
        radon_process = subprocess.run(
            ['radon', 'cc', UPLOAD_FOLDER, '-j'], # 'cc' for cyclomatic complexity, '-j' for JSON
            capture_output=True, text=True, check=False
        )
        # Radon's JSON output is a dictionary of files; we'll flatten it for the frontend
        radon_raw_results = json.loads(radon_process.stdout) if radon_process.stdout else {}
        radon_results = []
        for file_path, functions in radon_raw_results.items():
            for func in functions:
                # Add file path to each function object
                func['file_path'] = file_path.replace('temp_uploads\\', '')
                radon_results.append(func)
    except json.JSONDecodeError:
        radon_results = [{"name": "Radon analysis failed to produce valid JSON.", "complexity": 0}]


    # --- Clean up temporary files ---
    for file_info in files:
         os.remove(os.path.join(UPLOAD_FOLDER, file_info['fileName']))
    
    # --- Combine all results ---
    final_results = {
        "pylint": pylint_results,
        "bandit": bandit_results.get("results", []),
        "radon": radon_results
    }

    return jsonify(final_results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)