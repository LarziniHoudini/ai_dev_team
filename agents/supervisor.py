import os
import json
import time
import subprocess
from dotenv import load_dotenv
from github import Github
import ollama

# 1. PATH CONFIGURATION
# base_dir is E:\AgenticAI\ai_dev_team\agents
base_dir = os.path.dirname(os.path.abspath(__file__))
# Load .env from the parent directory (root)
load_dotenv(os.path.join(base_dir, '..', '.env'))

# GitHub & Directory Setup
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
g = Github(GITHUB_TOKEN)
WORKSPACE_DIR = os.path.join(base_dir, '..', 'workspace')
CONFIG_FILE = os.path.join(base_dir, '..', 'active_config.json')

# Model Setup
PLANNER_MODEL = "llama3.1:8b"
CODER_MODEL = "qwen2.5-coder:7b"

def get_target_from_config():
    """Reads the repository selected in the Web UI."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return data.get("target_repo")
        except Exception as e:
            print(f"[!] Error reading config: {e}")
    return None

def clone_repo(repo_full_name):
    """Clones the target repo into the workspace if it doesn't exist."""
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(WORKSPACE_DIR)
        
    repo_name = repo_full_name.split('/')[-1]
    repo_path = os.path.join(WORKSPACE_DIR, repo_name)
    
    if not os.path.exists(repo_path):
        print(f"[*] Cloning {repo_full_name} into workspace...")
        subprocess.run(["git", "clone", f"https://github.com/{repo_full_name}.git", repo_path], check=True)
    else:
        print(f"[*] Repository {repo_name} already exists in workspace.")
    return repo_path

def generate_research_plan(issue_title, issue_body):
    """Agent 1: Llama 3.1 analyzes the GitHub issue."""
    print(f"\n[*] Consulting {PLANNER_MODEL} for a research plan...")
    prompt = f"""
    You are a Senior Lead Developer. Analyze this GitHub issue and provide a technical implementation plan.
    ISSUE TITLE: {issue_title}
    ISSUE BODY: {issue_body}
    
    Provide your plan in bullet points, focusing on which files to check and logic changes.
    """
    response = ollama.generate(model=PLANNER_MODEL, prompt=prompt)
    return response['response']

def execute_coding_task(plan, repo_path):
    """Agent 2: Qwen 2.5 Coder generates the actual code suggestions."""
    print(f"[*] Consulting {CODER_MODEL} for code changes...")
    prompt = f"""
    You are an Expert Coder. Based on the following research plan and the code located at {repo_path}, 
    generate the specific code changes needed.
    
    PLAN: {plan}
    
    Output the code changes clearly in Markdown blocks.
    """
    response = ollama.generate(model=CODER_MODEL, prompt=prompt)
    return response['response']

def supervisor_loop():
    """Main control loop that waits for UI input and user commands."""
    print("=== Supervisor Agent is Online ===")
    
    while True:
        repo_name = get_target_from_config()
        
        if not repo_name:
            print("[?] No repo selected in Web UI. Waiting...", end="\r")
            time.sleep(5)
            continue

        print(f"\n\n[!] ACTIVE REPO: {repo_name}")
        try:
            repo = g.get_repo(repo_name)
            # Only pull issues labeled as bugs or enhancements
            issues = [i for i in repo.get_issues(state='open') 
                      if any(l.name.lower() in ['bug', 'enhancement'] for l in i.labels)]
            
            if not issues:
                print(f"[!] No open bug/enhancement issues found in {repo_name}.")
                time.sleep(10)
                continue

            for issue in issues:
                print(f"\n{'='*60}")
                print(f"TASK: #{issue.number} - {issue.title}")
                print(f"{'='*60}")
                
                # TRIGGER 1: RESEARCHER
                cmd = input(f"Press 'r' to trigger RESEARCHER (Llama 3.1) or 's' to skip: ").lower()
                if cmd == 'r':
                    repo_path = clone_repo(repo_name)
                    plan = generate_research_plan(issue.title, issue.body)
                    print(f"\n[RESEARCH PLAN FROM LLAMA]:\n{plan}")
                    
                    # TRIGGER 2: CODER
                    cmd = input(f"\nPress 'c' to trigger CODER (Qwen 2.5) or 's' to skip: ").lower()
                    if cmd == 'c':
                        suggestions = execute_coding_task(plan, repo_path)
                        print(f"\n[CODE SUGGESTIONS FROM QWEN]:\n{suggestions}")
                
                print(f"\n[*] Finished processing Issue #{issue.number}.")
            
            print("\n[*] All issues for this repo processed. Waiting for new tasks...")
            time.sleep(15)

        except Exception as e:
            print(f"\n[ERROR]: {e}")
            time.sleep(5)

if __name__ == "__main__":
    supervisor_loop()