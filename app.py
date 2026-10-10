from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
import os, json, time
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIG ---
UPLOAD_FOLDER = 'uploads'
DATA_FOLDER = 'data'
DB_FILE = os.path.join(DATA_FOLDER, 'db.json')
ALLOWED_EXT = {'pdf','jpg','jpeg','png','doc','docx','ppt','pptx','zip'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Create DB if not exists
if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w') as f:
        json.dump({"students":[],"tasks":[],"uploads":[]}, f, indent=2)

def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"students":[],"tasks":[],"uploads":[]}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

# --- MAIN PAGES ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/sw.js')
def sw():
    return send_from_directory('.', 'sw.js')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- API: STUDENTS ---
@app.route('/api/students', methods=['GET'])
def get_students():
    db = load_db()
    return jsonify(db['students'])

@app.route('/api/students', methods=['POST'])
def add_student():
    db = load_db()
    data = request.json
    if any(s['id'] == data['id'] for s in db['students']):
        return jsonify({"error":"Already exists"}), 400
    db['students'].append(data)
    save_db(db)
    return jsonify({"ok":True})

# --- API: TASKS ---
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    db = load_db()
    return jsonify(db['tasks'])

@app.route('/api/tasks', methods=['POST'])
def add_task():
    db = load_db()
    data = request.json
    data['id'] = int(time.time()*1000)
    # Clean type - ensure no subject name (just as you requested)
    db['tasks'].append(data)
    save_db(db)
    return jsonify({"ok":True, "id":data['id']})

# --- API: UPLOADS (WITH AUTO DEPOSITION TIME) ---
@app.route('/api/uploads', methods=['GET'])
def get_uploads():
    db = load_db()
    return jsonify(db['uploads'])

@app.route('/api/upload', methods=['POST'])
def upload_file():
    db = load_db()

    student_id = request.form.get('student_id')
    student_name = request.form.get('student_name')
    student_year = request.form.get('student_year')
    task_id = request.form.get('task_id')
    task_type = request.form.get('task_type')
    task_title = request.form.get('task_title')
    task_due = request.form.get('task_due')
    sub_date = request.form.get('sub_date') # user selected date

    # Validation
    if 'file' not in request.files:
        return jsonify({"error":"No file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error":"No filename"}), 400

    # Secure save
    filename = f"{int(time.time())}_{secure_filename(file.filename)}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # AUTO DEPOSITION TIME - Server Time
    now = datetime.now()
    depositionTime = now.strftime("%d %b %Y, %I:%M:%S %p") # e.g. 11 Oct 2026, 10:45:32 AM
    depositionISO = now.isoformat()

    # Calculate status
    try:
        due_dt = datetime.strptime(task_due, "%Y-%m-%d")
        sub_dt = datetime.strptime(sub_date, "%Y-%m-%d")
        diff = (sub_dt - due_dt).days
        status = "On Time" if diff <= 0 else f"Late {diff}d"
    except:
        status = "On Time"

    record = {
        "id": int(time.time()*1000),
        "student": {"id":student_id, "name":student_name, "year":student_year},
        "task": {"id":task_id, "type":task_type, "title":task_title, "due":task_due},
        "subDateInput": sub_date,
        "fileName": file.filename,
        "savedName": filename,
        "filePath": f"/uploads/{filename}",
        "status": status,
        "depositionTime": depositionTime,
        "depositionISO": depositionISO,
        "received": False,
        "marks": "",
        "remarks": "",
        "receivedAt": ""
    }

    db['uploads'].append(record)
    save_db(db)
    return jsonify({"ok":True, "depositionTime":depositionTime, "record":record})

# --- API: TEACHER ACTIONS ---
@app.route('/api/received', methods=['POST'])
def mark_received():
    db = load_db()
    data = request.json
    uid = data.get('id')
    for u in db['uploads']:
        if u['id'] == uid:
            u['received'] = True
            u['marks'] = data.get('marks','')
            u['remarks'] = data.get('remarks','')
            u['receivedAt'] = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
            save_db(db)
            return jsonify({"ok":True})
    return jsonify({"error":"Not found"}), 404

@app.route('/api/delete', methods=['POST'])
def delete_upload():
    db = load_db()
    data = request.json
    uid = data.get('id')
    # Delete file from disk
    for u in db['uploads']:
        if u['id'] == uid and 'savedName' in u:
            try: os.remove(os.path.join(UPLOAD_FOLDER, u['savedName']))
            except: pass
    db['uploads'] = [u for u in db['uploads'] if u['id']!= uid]
    save_db(db)
    return jsonify({"ok":True})

# --- RUN ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)