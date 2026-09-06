import os, io, csv, sqlite3, uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","uranas-change-this")
DB=os.environ.get("DATABASE_PATH","uranas.db")
UPLOAD=os.path.join("static","uploads")
os.makedirs(UPLOAD,exist_ok=True)
EXT={"csv","xlsx","xls"}

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=conn()
    c.execute("""CREATE TABLE IF NOT EXISTS clients(
      id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,county TEXT DEFAULT '',
      bins INTEGER DEFAULT 0,debt REAL DEFAULT 0,phone TEXT DEFAULT '',notes TEXT DEFAULT '',
      next_service TEXT DEFAULT '',updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(name,county))""")
    c.execute("""CREATE TABLE IF NOT EXISTS media(
      id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,title TEXT NOT NULL,
      filename TEXT NOT NULL,caption TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS notifications(
      id INTEGER PRIMARY KEY AUTOINCREMENT,client_id INTEGER,service_date TEXT,
      message TEXT,channel TEXT DEFAULT 'SMS/WhatsApp',created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.commit(); c.close()

def norm(x): return ''.join(ch.lower() for ch in str(x or '').strip() if ch.isalnum())
def get(row,names):
    d={norm(k):v for k,v in row.items()}
    for n in names:
        if norm(n) in d:return d[norm(n)]
    return ""
def num(x):
    try:return float(str(x).replace(",","").strip() or 0)
    except:return 0

def parse(f):
    ext=secure_filename(f.filename).rsplit(".",1)[-1].lower()
    if ext not in EXT: raise ValueError("Upload CSV, XLSX or XLS.")
    raw=f.read()
    if ext=="csv":
        return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig",errors="replace"))))
    import openpyxl
    wb=openpyxl.load_workbook(io.BytesIO(raw),data_only=True,read_only=True)
    rows=list(wb.active.values)
    if not rows:return []
    heads=[str(x or '').strip() for x in rows[0]]
    return [{heads[i]:(r[i] if i<len(r) else '') for i in range(len(heads))} for r in rows[1:]]

@app.route("/")
def home():
    c=conn()
    clients=c.execute("SELECT * FROM clients ORDER BY county,name").fetchall()
    stats=c.execute("SELECT COUNT(*) n,COALESCE(SUM(bins),0) bins,COALESCE(SUM(debt),0) debt FROM clients").fetchone()
    media=c.execute("SELECT * FROM media ORDER BY id DESC").fetchall()
    c.close()
    return render_template("dashboard.html",clients=clients,stats=stats,media=media)

@app.route("/admin/import",methods=["GET","POST"])
def import_clients():
    if request.method=="POST":
        f=request.files.get("file")
        if not f or not f.filename: flash("Select a spreadsheet first.","error"); return redirect(request.url)
        try: rows=parse(f)
        except Exception as e: flash(str(e),"error"); return redirect(request.url)
        c=conn(); added=updated=skipped=0
        for r in rows:
            name=str(get(r,["facility name","client name","name","customer","business","school"])).strip()
            if not name: skipped+=1; continue
            county=str(get(r,["county","region","location","area"])).strip()
            bins=int(num(get(r,["number of bins","bins","no of bins","quantity"])))
            debt=num(get(r,["debt","debts","balance","amount due"]))
            phone=str(get(r,["contact number","contact","phone","phone number","mobile"])).strip()
            service=str(get(r,["next service","service date","next service date"])).strip()
            notes=str(get(r,["notes","remarks","comment"])).strip()
            old=c.execute("SELECT id FROM clients WHERE lower(name)=lower(?) AND lower(county)=lower(?)",(name,county)).fetchone()
            now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if old:
                c.execute("UPDATE clients SET bins=?,debt=?,phone=?,notes=?,next_service=?,updated_at=? WHERE id=?",
                          (bins,debt,phone,notes,service,now,old["id"])); updated+=1
            else:
                c.execute("INSERT INTO clients(name,county,bins,debt,phone,notes,next_service,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                          (name,county,bins,debt,phone,notes,service,now)); added+=1
        c.commit(); c.close()
        flash(f"Import complete — {added} added, {updated} updated, {skipped} skipped.","success")
        return redirect(request.url)
    return render_template("import.html")

@app.route("/admin/media",methods=["POST"])
def upload_media():
    f=request.files.get("image")
    kind=request.form.get("kind","bin")
    title=request.form.get("title","").strip() or "Uranas Image"
    caption=request.form.get("caption","").strip()
    if not f or not f.filename: flash("Choose an image.","error"); return redirect(url_for("home"))
    ext=secure_filename(f.filename).rsplit(".",1)[-1].lower()
    if ext not in {"jpg","jpeg","png","webp"}: flash("Images must be JPG, PNG or WEBP.","error"); return redirect(url_for("home"))
    name=f"{uuid.uuid4().hex}.{ext}"; f.save(os.path.join(UPLOAD,name))
    c=conn(); c.execute("INSERT INTO media(kind,title,filename,caption) VALUES(?,?,?,?)",(kind,title,name,caption)); c.commit(); c.close()
    flash(f"{kind.title()} image uploaded.","success"); return redirect(url_for("home"))

@app.route("/admin/notify/<int:cid>",methods=["POST"])
def notify(cid):
    c=conn(); client=c.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    if not client: c.close(); flash("Client not found.","error"); return redirect(url_for("home"))
    date=request.form.get("service_date") or client["next_service"] or datetime.now().strftime("%Y-%m-%d")
    message=request.form.get("message") or f"Hello {client['name']}, this is a reminder from Uranas Global Services that your service is due on {date}. Thank you."
    c.execute("INSERT INTO notifications(client_id,service_date,message) VALUES(?,?,?)",(cid,date,message))
    c.commit(); c.close()
    # No fake SMS is sent here. The client's stored phone is the intended recipient.
    flash(f"Notification prepared for {client['name']} — {client['phone'] or 'no client number saved'}. Connect an SMS/WhatsApp provider when ready.","success")
    return redirect(url_for("home"))

@app.route("/admin/export")
def export():
    c=conn(); rows=c.execute("SELECT name,county,bins,debt,phone,next_service,notes FROM clients ORDER BY county,name").fetchall(); c.close()
    s=io.StringIO(); w=csv.writer(s); w.writerow(["Facility Name","County","Number of Bins","Debt","Client Phone","Next Service","Notes"])
    for r in rows:w.writerow(list(r))
    b=io.BytesIO(s.getvalue().encode("utf-8-sig")); b.seek(0)
    return send_file(b,as_attachment=True,download_name="uranas_clients.csv",mimetype="text/csv")

@app.route("/health")
def health(): return {"status":"ok"}

init()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
