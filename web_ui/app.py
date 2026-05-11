import token

from flask import Flask, render_template, request, redirect
from flask.cli import load_dotenv
from github import Github
import os

app = Flask(__name__)

# --- HARD-CODED CONFIG (Experimentation Mode) ---
load_dotenv()
g = Github(os.getenv("GITHUB_TOKEN"))


# Persistent state for the session
current_repo_name = None
repo_list = []
issue_list = []

@app.route('/')
def index():
    return render_template('index.html', 
                           repos=repo_list, 
                           issues=issue_list, 
                           selected_repo=current_repo_name)

@app.route('/refresh_repos', methods=['POST'])
def refresh_repos():
    global repo_list
    try:
        # Fetching your repositories
        repo_list = [repo.full_name for repo in g.get_user().get_repos()]
        repo_list.sort()
    except Exception as e:
        print(f"GitHub Error: {e}")
    return redirect('/')

@app.route('/fetch_issues', methods=['POST'])
def fetch_issues():
    global issue_list, current_repo_name
    repo_full_name = request.form.get('repository')
    if not repo_full_name: return redirect('/')
    
    current_repo_name = repo_full_name
    return fetch_issues_logic(repo_full_name)

@app.route('/create_issue', methods=['POST'])
def create_issue():
    if not current_repo_name: return redirect('/')
    
    title = request.form.get('title')
    body = request.form.get('description')
    label_type = request.form.get('category') # 'bug' or 'enhancement'
    
    try:
        repo = g.get_repo(current_repo_name)
        repo.create_issue(title=title, body=body, labels=[label_type])
    except Exception as e:
        print(f"Error creating issue: {e}")
    
    return fetch_issues_logic(current_repo_name)

@app.route('/close_issue/<int:issue_id>', methods=['POST'])
def close_issue(issue_id):
    if current_repo_name:
        try:
            repo = g.get_repo(current_repo_name)
            issue = repo.get_issue(number=issue_id)
            issue.edit(state='closed')
        except Exception as e:
            print(f"Error closing issue: {e}")
    return fetch_issues_logic(current_repo_name)

def fetch_issues_logic(repo_name):
    global issue_list, current_repo_name
    current_repo_name = repo_name
    try:
        repo = g.get_repo(repo_name)
        raw_issues = repo.get_issues(state='open')
        
        issue_list = []
        for i in raw_issues:
            labels = [l.name.lower() for l in i.labels]
            # Only show if it has the right labels
            if any(label in ['bug', 'enhancement'] for label in labels):
                issue_list.append({
                    'id': i.number,
                    'title': i.title,
                    'body': i.body if i.body else "",
                    'labels': labels
                })
    except Exception as e:
        print(f"Error fetching issues: {e}")
    return redirect('/')

if __name__ == '__main__':
    print("\nStarting Web UI on http://127.0.0.1:5000")
    app.run(debug=True)