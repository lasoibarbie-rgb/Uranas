import os, csv, io, sqlite3, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from werkzeug.utils import secure_filename

BASE=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE,"uranas.db")
UPLOAD_ROOT=os.path.join(BASE,"uploads")
ALLOWED_IMAGES={"jpg","jpeg","png","webp","gif"}
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY",secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"]=15*1024*1024
ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME","admin")
ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD","change-me-now")

def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS clients(
      id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT,email TEXT,
      location TEXT,service TEXT,notes TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS gallery(
      id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT NOT NULL,title TEXT,description TEXT,
      filename TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS bins(
      id INTEGER PRIMARY KEY AUTOINCREMENT,client_name TEXT,location TEXT,bin_type TEXT,
      serial_number TEXT,status TEXT DEFAULT 'Active',notes TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS import_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,filename TEXT,rows_imported INTEGER,created_at TEXT NOT NULL);
    """); c.commit(); c.close()

def admin_required(f):
    @wraps(f)
    def w(*a,**kw):
        if not session.get("admin"): return redirect(url_for("login",next=request.path))
        return f(*a,**kw)
    return w

@app.context_processor
def ctx(): return {"logged_in":bool(session.get("admin"))}

@app.route("/")
def index():
    c=db()
    bins=c.execute("SELECT * FROM gallery WHERE category='bin' ORDER BY id DESC").fetchall()
    bnb=c.execute("SELECT * FROM gallery WHERE category='bnb' ORDER BY id DESC").fetchall()
    c.close(); return render_template("index.html",bins=bins,bnb=bnb)

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        if request.form.get("username")==ADMIN_USERNAME and request.form.get("password")==ADMIN_PASSWORD:
            session["admin"]=True; return redirect(request.args.get("next") or url_for("admin"))
        flash("Incorrect admin username or password.","error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    c=db()
    clients=c.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    gallery=c.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall()
    bins=c.execute("SELECT * FROM bins ORDER BY id DESC").fetchall()
    imports=c.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 10").fetchall()
    c.close(); return render_template("admin.html",clients=clients,gallery=gallery,bins=bins,imports=imports)

@app.route("/admin/client/add",methods=["POST"])
@admin_required
def add_client():
    c=db(); c.execute("""INSERT INTO clients(name,phone,email,location,service,notes,created_at)
    VALUES(?,?,?,?,?,?,?)""",(request.form.get("name","").strip(),request.form.get("phone","").strip(),
    request.form.get("email","").strip(),request.form.get("location","").strip(),
    request.form.get("service","").strip(),request.form.get("notes","").strip(),datetime.utcnow().isoformat()))
    c.commit(); c.close(); flash("Client added. Client information is admin-only.","success"); return redirect(url_for("admin"))

@app.route("/admin/client/delete/<int:client_id>",methods=["POST"])
@admin_required
def delete_client(client_id):
    c=db(); c.execute("DELETE FROM clients WHERE id=?",(client_id,)); c.commit(); c.close()
    flash("Client deleted.","success"); return redirect(url_for("admin"))

@app.route("/admin/gallery/upload",methods=["POST"])
@admin_required
def upload_gallery():
    category=request.form.get("category")
    f=request.files.get("image")
    if category not in {"bin","bnb"} or not f or not f.filename:
        flash("Choose a category and image.","error"); return redirect(url_for("admin"))
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_IMAGES:
        flash("Only JPG, JPEG, PNG, WEBP or GIF images are allowed.","error"); return redirect(url_for("admin"))
    filename=secrets.token_hex(8)+"_"+secure_filename(f.filename)
    folder=os.path.join(UPLOAD_ROOT,category); os.makedirs(folder,exist_ok=True)
    f.save(os.path.join(folder,filename))
    c=db(); c.execute("""INSERT INTO gallery(category,title,description,filename,created_at)
    VALUES(?,?,?,?,?)""",(category,request.form.get("title","").strip(),
    request.form.get("description","").strip(),filename,datetime.utcnow().isoformat()))
    c.commit(); c.close()
    flash(f"{category.upper()} image uploaded and published.","success"); return redirect(url_for("admin"))

@app.route("/admin/gallery/delete/<int:item_id>",methods=["POST"])
@admin_required
def delete_gallery(item_id):
    c=db(); item=c.execute("SELECT * FROM gallery WHERE id=?",(item_id,)).fetchone()
    if item:
        p=os.path.join(UPLOAD_ROOT,item["category"],item["filename"])
        if os.path.exists(p): os.remove(p)
        c.execute("DELETE FROM gallery WHERE id=?",(item_id,)); c.commit()
    c.close(); flash("Image removed.","success"); return redirect(url_for("admin"))

@app.route("/admin/bin/add",methods=["POST"])
@admin_required
def add_bin():
    c=db(); c.execute("""INSERT INTO bins(client_name,location,bin_type,serial_number,status,notes,created_at)
    VALUES(?,?,?,?,?,?,?)""",(request.form.get("client_name","").strip(),request.form.get("location","").strip(),
    request.form.get("bin_type","").strip(),request.form.get("serial_number","").strip(),
    request.form.get("status","Active"),request.form.get("notes","").strip(),datetime.utcnow().isoformat()))
    c.commit(); c.close(); flash("Bin record added.","success"); return redirect(url_for("admin"))

@app.route("/admin/bin/delete/<int:bin_id>",methods=["POST"])
@admin_required
def delete_bin(bin_id):
    c=db(); c.execute("DELETE FROM bins WHERE id=?",(bin_id,)); c.commit(); c.close()
    flash("Bin record deleted.","success"); return redirect(url_for("admin"))

@app.route("/admin/import",methods=["POST"])
@admin_required
def import_file():
    f=request.files.get("data_file")
    if not f or not f.filename:
        flash("Select a CSV or Excel file.","error"); return redirect(url_for("admin"))
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in {"csv","xlsx","xls"}:
        flash("Use CSV, XLS or XLSX.","error"); return redirect(url_for("admin"))
    try:
        if ext=="csv":
            rows=list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
        else:
            import pandas as pd
            rows=pd.read_excel(io.BytesIO(f.read())).fillna("").to_dict(orient="records")
        c=db(); count=0
        for raw in rows:
            r={str(k).strip().lower():str(v).strip() for k,v in dict(raw).items()}
            name=r.get("name") or r.get("client name") or r.get("client_name")
            if not name: continue
            c.execute("""INSERT INTO clients(name,phone,email,location,service,notes,created_at)
            VALUES(?,?,?,?,?,?,?)""",(name,r.get("phone") or r.get("phone number") or r.get("client phone"),
            r.get("email"),r.get("location") or r.get("address"),
            r.get("service") or r.get("services"),r.get("notes") or r.get("remarks"),datetime.utcnow().isoformat()))
            count+=1
        c.execute("INSERT INTO import_log(filename,rows_imported,created_at) VALUES(?,?,?)",
                  (secure_filename(f.filename),count,datetime.utcnow().isoformat()))
        c.commit(); c.close(); flash(f"Import complete: {count} client records added. Admin-only.","success")
    except Exception:
        flash("Import failed. Check that the file has a Name column and valid CSV/Excel formatting.","error")
    return redirect(url_for("admin"))

@app.route("/uploads/<category>/<path:filename>")
def uploaded(category,filename):
    if category not in {"bin","bnb"}: abort(404)
    return send_from_directory(os.path.join(UPLOAD_ROOT,category),filename)

init_db()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
