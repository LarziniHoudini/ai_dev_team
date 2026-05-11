from flask import Flask, render_template, request, redirect
import pandas as pd
import os

app = Flask(__name__)
EXCEL_FILE = 'tasks_backlog.xlsx'

def initialize_excel():
    """Creates the excel file with correct sheets if it doesn't exist."""
    if not os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            pd.DataFrame(columns=['Title', 'Description', 'Status']).to_excel(writer, sheet_name='Features', index=False)
            pd.DataFrame(columns=['Title', 'Description', 'Status']).to_excel(writer, sheet_name='Bugs', index=False)
        print(f"Created new database: {EXCEL_FILE}")

def get_all_tasks():
    """Reads all sheets and returns a combined list for the UI."""
    initialize_excel()
    try:
        with pd.ExcelFile(EXCEL_FILE) as xls:
            f_df = pd.read_excel(xls, sheet_name='Features')
            b_df = pd.read_excel(xls, sheet_name='Bugs')
        
        # Add a helper 'type' key so the HTML knows which CSS class to use
        features = f_df.to_dict('records')
        for item in features: item['type'] = 'Features'
        
        bugs = b_df.to_dict('records')
        for item in bugs: item['type'] = 'Bugs'
        
        return features + bugs
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return []

@app.route('/')
def index():
    tasks = get_all_tasks()
    return render_template('index.html', tasks=tasks)

@app.route('/add', methods=['POST'])
def add():
    category = request.form.get('category') # 'Features' or 'Bugs'
    title = request.form.get('title')
    description = request.form.get('description')
    
    try:
        # 1. Load everything into memory to avoid partial overwrites
        with pd.ExcelFile(EXCEL_FILE) as xls:
            features_df = pd.read_excel(xls, 'Features')
            bugs_df = pd.read_excel(xls, 'Bugs')
        
        # 2. Create the new task entry
        new_row = pd.DataFrame([{
            'Title': title, 
            'Description': description, 
            'Status': 'Pending'
        }])
        
        # 3. Update the specific dataframe
        if category == 'Features':
            features_df = pd.concat([features_df, new_row], ignore_index=True)
        else:
            bugs_df = pd.concat([bugs_df, new_row], ignore_index=True)
            
        # 4. Save the entire workbook back to disk
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            features_df.to_excel(writer, sheet_name='Features', index=False)
            bugs_df.to_excel(writer, sheet_name='Bugs', index=False)
        
        print(f"Successfully added {category}: {title}")
            
    except PermissionError:
        print("ERROR: Could not save! Please close 'tasks_backlog.xlsx' in Excel first.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
            
    return redirect('/')

if __name__ == '__main__':
    initialize_excel()
    print("\n" + "="*30)
    print("WEB UI: http://127.0.0.1:5000")
    print("="*30 + "\n")
    app.run(debug=True)