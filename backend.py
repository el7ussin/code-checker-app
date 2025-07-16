import os
import json
import subprocess
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS

# Make sure your API Key is correct here
API_KEY = 'AIzaSyCyDG2Pbyf6ZckrHMVPVYwAS7ORME-UCS4'
genai.configure(api_key=API_KEY)

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/analyze', methods=['POST'])
def analyze_code():
    files = request.get_json()
    if not files:
        return jsonify({"error": "No files provided"}), 400

    file_paths_to_analyze = []
    for file_info in files:
        file_path = os.path.join(UPLOAD_FOLDER, file_info['fileName'])
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_info['content'])
        file_paths_to_analyze.append(file_path)
    
    # --- Run Pylint ---
    pylint_results = []
    try:
        pylint_process = subprocess.run(
            ['pylint'] + file_paths_to_analyze + ['--output-format=json'],
            capture_output=True, text=True, check=False
        )
        pylint_results = json.loads(pylint_process.stdout) if pylint_process.stdout else []
    except json.JSONDecodeError:
        pylint_results = [{"message": "Pylint analysis failed.", "type": "fatal"}]

    # --- Run Bandit ---
    bandit_results = {"results": []}
    try:
        bandit_process = subprocess.run(
            ['bandit', '-r', UPLOAD_FOLDER, '-f', 'json'],
            capture_output=True, text=True, check=False
        )
        bandit_results = json.loads(bandit_process.stdout) if bandit_process.stdout else {"results": []}
    except json.JSONDecodeError:
        bandit_results = {"results": [{"issue_text": "Bandit analysis failed."}]}

    # --- Run Radon ---
    radon_results = []
    try:
        radon_process = subprocess.run(
            ['radon', 'cc'] + file_paths_to_analyze + ['-j'],
            capture_output=True, text=True, check=False
        )
        radon_raw_results = json.loads(radon_process.stdout) if radon_process.stdout else {}
        for file_path, functions in radon_raw_results.items():
            for func in functions:
                func['file_path'] = os.path.basename(file_path)
                radon_results.append(func)
    except json.JSONDecodeError:
        radon_results = [{"name": "Radon analysis failed.", "complexity": 0}]

    # --- Clean up ---
    for file_path in file_paths_to_analyze:
        os.remove(file_path)
    
    final_results = {
        "pylint": pylint_results,
        "bandit": bandit_results.get("results", []),
        "radon": radon_results
    }
    return jsonify(final_results)

# --- AI Suggestion Route ---
@app.route('/get-suggestion', methods=['POST'])
def get_suggestion():
    data = request.get_json()
    error_message = data.get('errorMessage')
    code_context = data.get('codeContext')

    if not error_message or not code_context:
        return jsonify({"error": "Missing error message or code context"}), 400

    try:
        # THIS IS THE FIX: Changed 'gemini-pro' to 'gemini-1.5-flash'
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        As a Python expert, analyze the following static analysis error message and the related code.
        Provide a helpful suggestion in two parts:
        1.  **Explanation:** Briefly explain what the error means in simple terms.
        2.  **Suggestion:** Provide a corrected version of the code snippet to fix the issue.

        **Error Message:**
        "{error_message}"

        **Code Context:**
        ```python
        {code_context}
        ```

        Format your response clearly.
        """
        response = model.generate_content(prompt)
        return jsonify({"suggestion": response.text})
    except Exception as e:
        print(f"AN ERROR OCCURRED IN /get-suggestion: {str(e)}")
        return jsonify({"error": f"Failed to get suggestion from AI: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)