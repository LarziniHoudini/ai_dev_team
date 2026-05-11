from flask import Flask, render_template, request, redirect
from github import Github
import os

app = Flask(__name__)

# --- CONFIG ---
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"
g = Github(GITHUB_TOKEN)

# Temporary memory to store fetched data
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
    repo_list = [repo.full_name for repo in g.get_user().get_repos()]
    repo_list.sort()
    return redirect('/')

@app.route('/fetch_issues', methods=['POST'])
def fetch_issues():
    global issue_list, current_repo_name
    repo_full_name = request.form.get('repository')
    current_repo_name = repo_full_name
    
    repo = g.get_repo(repo_full_name)
    # Fetch open issues
    raw_issues = repo.get_issues(state='open')
    
    issue_list = []
    for i in raw_issues:
        # Filter for specifically 'bug' or 'enhancement'
        labels = [l.name.lower() for l in i.labels]
        if 'bug' in labels or 'enhancement' in labels:
            issue_list.append({
                'id': i.number,
                'title': i.title,
                'body': i.body,
                'labels': labels,
                'url': i.html_url
            })
    return redirect('/')

@app.route('/close_issue/<int:issue_id>', methods=['POST'])
def close_issue(issue_id):
    if current_repo_name:
        repo = g.get_repo(current_repo_name)
        issue = repo.get_issue(number=issue_id)
        issue.edit(state='closed')
        # Refresh the local list after closing
        return fetch_issues_logic(current_repo_name)
    return redirect('/')

def fetch_issues_logic(repo_name):
    # Helper to refresh list internally
    global issue_list
    repo = g.get_repo(repo_name)
    raw_issues = repo.get_issues(state='open')
    issue_list = [{
        'id': i.number, 'title': i.title, 'body': i.body, 
        'labels': [l.name for l in i.labels]
    } for i in raw_issues if any(l.name.lower() in ['bug', 'enhancement'] for l in i.labels)]
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)