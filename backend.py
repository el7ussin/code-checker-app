import os
import json
import subprocess
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-super-secret-key-that-you-should-change'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- GitHub OAuth App Credentials ---
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')

# --- Gemini API Configuration ---
API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyCyDG2Pbyf6ZckrHMVPVYwAS7ORME-UCS4')
genai.configure(api_key=API_KEY)

UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Initializations ---
CORS(app, supports_credentials=True)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150))
    github_id = db.Column(db.String(150), unique=True, nullable=True)
    github_token = db.Column(db.String(200), nullable=True)
    reports = db.relationship('Report', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Auth Routes ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user)
        return jsonify({"message": "Logged in successfully", "username": user.username}), 200
    return jsonify({"error": "Invalid username or password"}), 401

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/status')
def status():
    if current_user.is_authenticated:
        return jsonify({"logged_in": True, "username": current_user.username})
    return jsonify({"logged_in": False})

# --- GitHub OAuth ---
@app.route('/login/github')
def github_login():
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}"
    return redirect(github_auth_url)

@app.route('/login/github/callback')
def github_callback():
    code = request.args.get('code')
    token_url = 'https://github.com/login/oauth/access_token'
    headers = {'Accept': 'application/json'}
    payload = {
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'code': code
    }
    token_res = requests.post(token_url, headers=headers, json=payload)
    token_json = token_res.json()
    access_token = token_json.get('access_token')
    if not access_token:
        return redirect('https://code-checker-app.vercel.app?error=github_login_failed')

    user_res = requests.get('https://api.github.com/user', headers={'Authorization': f'token {access_token}'})
    user_json = user_res.json()
    github_id = str(user_json.get('id'))
    username = user_json.get('login')

    user = User.query.filter_by(github_id=github_id).first()
    if not user:
        user = User(username=username, github_id=github_id)
        db.session.add(user)
    user.github_token = access_token
    db.session.commit()
    login_user(user)
    return redirect('https://code-checker-app.vercel.app')

@app.route('/get-repos')
@login_required
def get_repos():
    if not current_user.github_token:
        return jsonify({"error": "Not logged in with GitHub"}), 403
    headers = {'Authorization': f'token {current_user.github_token}'}
    repos_res = requests.get('https://api.github.com/user/repos?sort=updated&per_page=100', headers=headers)
    if repos_res.status_code != 200:
        return jsonify({"error": "Failed to fetch repos"}), 500
    repos_json = repos_res.json()
    return jsonify([{"name": repo['full_name']} for repo in repos_json])

# --- Analysis from Uploaded Files ---
@app.route('/analyze', methods=['POST'])
def analyze_code():
    files = request.get_json()
    if not files or not isinstance(files, list):
        return jsonify({"error": "No files provided"}), 400

    if len(files) > 20 or any(len(f['content']) > 10000 for f in files):
        return jsonify({"error": "Too many or too large files."}), 400

    file_paths_to_analyze = []
    for file_info in files:
        file_path = os.path.join(UPLOAD_FOLDER, file_info['fileName'])
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_info['content'])
        file_paths_to_analyze.append(file_path)

    # --- Pylint ---
    try:
        pylint_proc = subprocess.run(
            ['pylint'] + file_paths_to_analyze + ['--output-format=json'],
            capture_output=True, text=True, timeout=30
        )
        pylint_results = json.loads(pylint_proc.stdout) if pylint_proc.stdout else []
    except Exception:
        pylint_results = [{"message": "Pylint analysis failed", "type": "fatal"}]

    # --- Bandit ---
    try:
        bandit_proc = subprocess.run(
            ['bandit', '-r', UPLOAD_FOLDER, '-f', 'json'],
            capture_output=True, text=True, timeout=30
        )
        bandit_results = json.loads(bandit_proc.stdout).get("results", [])
    except Exception:
        bandit_results = [{"issue_text": "Bandit analysis failed"}]

    # --- Radon ---
    radon_results = []
    try:
        radon_proc = subprocess.run(
            ['radon', 'cc'] + file_paths_to_analyze + ['-j'],
            capture_output=True, text=True, timeout=30
        )
        raw = json.loads(radon_proc.stdout)
        for file_path, funcs in raw.items():
            for func in funcs:
                func['file_path'] = os.path.basename(file_path)
                radon_results.append(func)
    except Exception:
        radon_results = [{"name": "Radon analysis failed", "complexity": 0}]

    # --- Cleanup ---
    for path in file_paths_to_analyze:
        try:
            os.remove(path)
        except Exception:
            pass

    final_results = {
        "pylint": pylint_results,
        "bandit": bandit_results,
        "radon": radon_results
    }
    return jsonify(final_results)

# --- Suggestion Endpoint ---
@app.route('/get-suggestion', methods=['POST'])
def get_suggestion():
    data = request.get_json()
    error_message = data.get('errorMessage')
    code_context = data.get('codeContext')

    if not error_message or not code_context:
        return jsonify({"error": "Missing error message or code context"}), 400

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        As a Python expert, analyze the following static analysis error message and the related code.
        Provide a helpful suggestion in two parts:
        1. **Explanation**: What does this error mean?
        2. **Suggestion**: How can it be fixed?

        **Error Message:**
        "{error_message}"

        **Code Context:**
        ```python
        {code_context}
        ```
        """
        response = model.generate_content(prompt)
        return jsonify({"suggestion": getattr(response, 'text', 'No suggestion generated.')})
    except Exception as e:
        return jsonify({"error": f"AI suggestion failed: {str(e)}"}), 500

# --- Report Routes ---
@app.route('/save-report', methods=['POST'])
@login_required
def save_report():
    data = request.get_json()
    new_report = Report(content=json.dumps(data), author=current_user)
    db.session.add(new_report)
    db.session.commit()
    return jsonify({"message": "Report saved", "report_id": new_report.id}), 201

@app.route('/get-reports', methods=['GET'])
@login_required
def get_reports():
    reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.timestamp.desc()).all()
    return jsonify([
        {
            "id": r.id,
            "timestamp": r.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "content": json.loads(r.content)
        } for r in reports
    ]), 200

# --- Run Locally ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
