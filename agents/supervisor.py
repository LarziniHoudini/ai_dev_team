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

def generate_research_plan(issue_title, issue_body, repo_path):
    # 1. Get file list
    existing_files = []
    for root, dirs, files in os.walk(repo_path):
        if '.git' in dirs: dirs.remove('.git')
        for file in files:
            existing_files.append(os.path.relpath(os.path.join(root, file), repo_path))
    
    file_list_str = "\n".join(existing_files)

    # 2. Dynamic Context: Find the most likely file to read
    # We'll look for keywords in the issue to guess which file to 'read' for context
    potential_target = "index.html" # Default
    for f in existing_files:
        if any(word in f.lower() for word in issue_title.lower().split()):
            potential_target = f
            break
            
    file_content = ""
    target_path = os.path.join(repo_path, potential_target)
    if os.path.exists(target_path):
        with open(target_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

    print(f"\n[*] RESEARCHER is analyzing {potential_target} for context...")
    
    prompt = f"""
    You are a Pragmatic Senior Developer. 
    Task: {issue_title}
    Description: {issue_body}
    
    Available Files: 
    {file_list_str}
    
    Content of {potential_target}:
    {file_content}
    
    GUIDELINES:
    1. Identify the specific file(s) that need modification based on the evidence provided.
    2. Suggest the most direct technical solution. 
    3. Do NOT suggest infrastructure changes, package installs, or 'best practice' files (like separate CSS/JS) unless they already exist in the file list.
    4. Focus 100% on the logic/styling required to close the issue.
    5. Identify the EXACT file from the list above to modify.
    """
    
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

# --- UPDATED: THE ACTUAL WORKER ---
def write_to_disk(repo_path, ai_text):
    """This function now applies the changes directly to your file."""
    # Find the filename in the AI text or default to index.html
    match = re.search(r'### File: ([\w\./\-]+)', ai_text) or re.search(r'# ([\w\./\-]+\.\w+)', ai_text)
    target_file = match.group(1) if match else "index.html"
    
    full_path = os.path.normpath(os.path.join(repo_path, target_file))
    
    # Extract code from triple backticks
    code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', ai_text, re.DOTALL)
    if not code_blocks:
        print("[!] Error: No code blocks found in AI response. Cannot apply changes.")
        return

    new_content = code_blocks[0]
    
    print(f"\n[!] READY TO APPLY CHANGES TO: {full_path}")
    confirm = input("Are you sure you want to OVERWRITE this file? (y/n): ")
    
    if confirm.lower() == 'y':
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[SUCCESS] Changes applied to {target_file}!")
        except Exception as e:
            print(f"[ERROR] Failed to write to file: {e}")
    else:
        print("[*] Change cancelled by user.")

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
                    # plan = generate_research_plan(issue.title, issue.body)
                    plan = generate_research_plan(issue.title, issue.body, r_path)
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