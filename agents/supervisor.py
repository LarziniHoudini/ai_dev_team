import os
import json
import time
import subprocess
import re
from urllib import response
from click import prompt
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
    # 1. Get the CLEAN list of files (No venv, No .git)
    exclude_dirs = {'.git', 'venv', '__pycache__', '.env', 'node_modules'}
    all_files = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            all_files.append(os.path.relpath(os.path.join(root, file), repo_path))
    
    file_list_str = "\n".join(all_files)

    # --- PASS 1: ASK THE AI TO PICK THE FILE ---
    print("[*] Phase 1: Asking AI to locate the file...")
    pick_prompt = f"""
    Given this GitHub issue: "{issue_title} {issue_body}"
    And this list of files:
    {file_list_str}

    Which EXACT file path from the list above should be modified? 
    Respond with ONLY the file path, nothing else.
    """
    pick_response = ollama.generate(model=PLANNER_MODEL, prompt=pick_prompt)
    potential_target = pick_response.get('response', '').strip().split('\n')[0] 

    # --- NEW: HEAVY SANITIZATION ---
    # 1. Strip backticks, quotes, and whitespace
    potential_target = potential_target.replace('`', '').replace('"', '').replace("'", "").strip()
    # 2. Normalize slashes (Turn all \ into /)
    potential_target = potential_target.replace('\\', '/')

    # --- VALIDATION ---
    #if potential_target not in all_files:
    #    print(f"[!] AI suggested {potential_target}, but it's not in the file list. Defaulting to keyword search...")
    #    # (Insert your previous keyword search fallback here)
    #    potential_target = all_files[0] # Temporary fallback

    # --- NEW: SMART VALIDATION ---
    found_match = None
    for f in all_files:
        # Compare normalized versions of both
        if f.replace('\\', '/') == potential_target:
            found_match = f
            break
            
    if found_match:
        potential_target = found_match
        print(f"[*] MATCH CONFIRMED: {potential_target}")
    else:
        print(f"[!] AI suggested '{potential_target}', but list has '{all_files[0]}'.")
        # If the AI was close (e.g. it forgot a subfolder), let's try a partial match
        for f in all_files:
            if potential_target in f.replace('\\', '/'):
                potential_target = f
                print(f"[*] PARTIAL MATCH FOUND: {potential_target}")
                break

    # --- PASS 2: READ THE CONTENT ---
    file_content = ""
    target_path = os.path.normpath(os.path.join(repo_path, potential_target))
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            print(f"[*] TARGET IDENTIFIED: {potential_target}")
            print(f"[*] ACTUAL CODE LOADED into Researcher's memory.")
    except Exception as e:
        print(f"[!] FAILED TO READ: {target_path} - {e}")

    # --- PASS 3: GENERATE THE PLAN ---
    print(f"[*] Phase 2: Generating plan based on {potential_target} content...")
   # final_prompt = f"""
   # SOURCE CODE FOR {potential_target}:
   # ```
   # {file_content}

   # ISSUE: {issue_title}

   # TASK: Provide a technical plan to solve this issue using ONLY the code above. 
   # Explain exactly which CSS selectors or HTML tags to change.
   # """

# --- PASS 3: THE FINAL PLAN ---
    final_prompt = f"""
    ### CONTEXT ###
    You are a Senior Developer fixing a specific issue.
    ISSUE: {issue_title}
    GOAL: {issue_body}

    ### FILE TO MODIFY ###
    Path: {potential_target}

    ### SOURCE CODE ###
    // --- START OF FILE ---
    {file_content}
    // --- END OF FILE ---

    TASK: Provide a technical plan to solve this issue using ONLY the code above. 

    ### INSTRUCTIONS ###
    1. Only use the code provided above.
    2. Do NOT suggest new files or environment installs.
    3. Provide a step-by-step implementation plan for the Coder.
    """

    response = ollama.generate(model=PLANNER_MODEL, prompt=final_prompt)
    return response.get('response', str(response)), potential_target





    



    #INSTRUCTIONS:
    #1. Base your plan EXCLUSIVELY on the code provided between the 'START CODE' and 'END CODE' tags.
    #2. Do NOT mention venv, .git, or any folders outside of the workspace.
    #3. Provide the specific logic for the fix.
    #"""
    
def execute_coding_task(plan, repo_path, target_file):
    """Agent 2: Qwen 2.5 Coder reads the file and proposes the fix."""
    print(f"[*] CODER is reading {target_file} to prepare the fix...")
    
    # 1. Read the actual file content so the Coder sees what it's changing
    full_path = os.path.normpath(os.path.join(repo_path, target_file))
    file_content = ""
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        return f"Error reading file for coding: {e}"

    # 2. Ask the Coder to generate the NEW version of the file
    prompt = f"""
    You are an Expert Developer. 
    TARGET FILE: {target_file}
    
    CURRENT CONTENT:
    ```
    {file_content}
    PLAN TO IMPLEMENT:
    {plan}

    TASK:
    1. Apply the plan to the current content.
    2. Output the ENTIRE file content. No snippets. No placeholders.
    3. Start your response with '### File: {target_file}' followed by a code block.
    """

    response = ollama.generate(model=CODER_MODEL, prompt=prompt)
    return response.get('response', str(response))

#def execute_coding_task(plan):
 #   print(f"[*] CODER ({CODER_MODEL}) is writing code...")
#    prompt = f"Plan: {plan}\nGenerate the full code for the fix. Use markdown blocks."
#    response = ollama.generate(model=CODER_MODEL, prompt=prompt)
#    return response.get('response', str(response))

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
                    # plan = generate_research_plan(issue.title, issue.body, r_path)
                    plan, target_file = generate_research_plan(issue.title, issue.body, r_path)
                    print(f"\nPLAN:\n{plan}")
                    
                    if input("\nRun CODER? (y/n): ").lower() == 'y':
                        code = execute_coding_task(plan, r_path, target_file)
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