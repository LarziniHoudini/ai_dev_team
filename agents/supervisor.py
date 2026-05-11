import os
import json
import time
import subprocess
import re
from dotenv import load_dotenv
from github import Github
import ollama

# 1. PATH CONFIGURATION
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, '..', '.env'))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
g = Github(GITHUB_TOKEN)

WORKSPACE_DIR = os.path.normpath(os.path.join(base_dir, '..', 'workspace'))
CONFIG_FILE = os.path.normpath(os.path.join(base_dir, '..', 'active_config.json'))

PLANNER_MODEL = "llama3.1:8b"
CODER_MODEL = "qwen2.5-coder:7b"

def get_target_from_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return data.get("target_repo")
    except (json.JSONDecodeError, Exception):
        return None

def clone_repo(repo_full_name):
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(WORKSPACE_DIR)
    repo_name = repo_full_name.split('/')[-1]
    repo_path = os.path.join(WORKSPACE_DIR, repo_name)
    if not os.path.exists(repo_path):
        print(f"[*] Cloning {repo_full_name}...")
        subprocess.run(["git", "clone", f"https://github.com/{repo_full_name}.git", repo_path], check=True, shell=True)
    return os.path.abspath(repo_path)

def generate_research_plan(issue_title, issue_body):
    print(f"\n[*] RESEARCHER ({PLANNER_MODEL}) is thinking...")
    prompt = f"Technical Plan for: {issue_title}\nDetails: {issue_body}\nList files to modify."
    response = ollama.generate(model=PLANNER_MODEL, prompt=prompt)
    return response.get('response', str(response))

def execute_coding_task(plan):
    print(f"[*] CODER ({CODER_MODEL}) is writing code...")
    prompt = f"Plan: {plan}\nGenerate the full code for the fix. Use markdown blocks."
    response = ollama.generate(model=CODER_MODEL, prompt=prompt)
    return response.get('response', str(response))

def execute_review(plan, code):
    print(f"[*] REVIEWER ({PLANNER_MODEL}) is checking code...")
    prompt = f"Check this code against the plan:\nPLAN: {plan}\nCODE: {code}\nIf good, end with 'STATUS: PASSED'."
    response = ollama.generate(model=PLANNER_MODEL, prompt=prompt)
    return response.get('response', str(response))

def write_to_disk(repo_path, ai_text):
    match = re.search(r'### File: ([\w\./\-]+)', ai_text) or re.search(r'# ([\w\./\-]+\.\w+)', ai_text)
    suggested = match.group(1) if match else "fix_output.txt"
    
    print(f"\n[?] Suggested file: {suggested}")
    # Line 76 fix: ensured the input string and parenthesis are correctly closed
    user_file = input(f"Confirm filename (Enter for '{suggested}'): ") or suggested
    
    code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', ai_text, re.DOTALL)
    content = code_blocks[0] if code_blocks else ai_text
    
    full_path = os.path.join(repo_path, user_file)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[SUCCESS] Saved to {full_path}")

def supervisor_loop():
    print("=== AI DEV TEAM ONLINE ===")
    while True:
        repo_name = get_target_from_config()
        if not repo_name:
            print("[?] Waiting for UI selection...", end="\r")
            time.sleep(5)
            continue

        try:
            repo = g.get_repo(repo_name)
            issues = [i for i in repo.get_issues(state='open') if any(l.name.lower() in ['bug', 'enhancement'] for l in i.labels)]
            
            for issue in issues:
                print(f"\n>>> TASK: #{issue.number} {issue.title}")
                r_path = clone_repo(repo_name)
                
                if input("Run RESEARCHER? (y/n): ").lower() == 'y':
                    plan = generate_research_plan(issue.title, issue.body)
                    print(f"\nPLAN:\n{plan}")
                    
                    if input("\nRun CODER? (y/n): ").lower() == 'y':
                        code = execute_coding_task(plan)
                        print(f"\nCODE:\n{code}")
                        
                        if input("\nRun REVIEWER? (y/n): ").lower() == 'y':
                            review = execute_review(plan, code)
                            print(f"\nREVIEW:\n{review}")
                            
                            if "STATUS: PASSED" in review or input("Write anyway? (y/n): ").lower() == 'y':
                                write_to_disk(r_path, code)
            
            print("\n[*] Batch complete. Sleeping 30s...")
            time.sleep(30)
        except Exception as e:
            print(f"\n[ERROR]: {e}")
            time.sleep(10)

if __name__ == "__main__":
    supervisor_loop()