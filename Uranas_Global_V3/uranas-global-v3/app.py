import os, urllib.parse, base64, requests
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm

app=Flask(__name__)
app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","change-me")
db_url=os.getenv("DATABASE_URL","sqlite:///uranas.db")
if db_url.startswith("postgres://"): db_url=db_url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"]=db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
db=SQLAlchemy(app)

WHATSAPP_NUMBER="254114685152"
MPESA_TILL=os.getenv("MPESA_TILL","9393003")
MPESA_ENV=os.getenv("MPESA_ENV","sandbox")
MPESA_CALLBACK_BASE=os.getenv("MPESA_CALLBACK_BASE_URL","").rstrip("/")

class Client(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    phone=db.Column(db.String(50))
    email=db.Column(db.String(160))
    service=db.Column(db.String(120))
    notes=db.Column(db.Text)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    items=db.relationship("ServiceItem",backref="client",cascade="all, delete-orphan")
    invoices=db.relationship("Invoice",backref="client",cascade="all, delete-orphan")

class ServiceItem(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    client_id=db.Column(db.Integer,db.ForeignKey("client.id"),nullable=False)
    description=db.Column(db.String(200),nullable=False,default="Sanitary bin service")
    quantity=db.Column(db.Integer,nullable=False,default=1)
    unit_price=db.Column(db.Numeric(12,2),nullable=False,default=0)
    active=db.Column(db.Boolean,default=True)
    @property
    def amount(self): return Decimal(str(self.quantity))*Decimal(str(self.unit_price))

class Invoice(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    client_id=db.Column(db.Integer,db.ForeignKey("client.id"),nullable=False)
    invoice_no=db.Column(db.String(40),unique=True)
    description=db.Column(db.String(240),nullable=False)
    total=db.Column(db.Numeric(12,2),nullable=False,default=0)
    paid=db.Column(db.Numeric(12,2),nullable=False,default=0)
    due_date=db.Column(db.Date)
    period=db.Column(db.String(30))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    payments=db.relationship("Payment",backref="invoice",cascade="all, delete-orphan")
    @property
    def balance(self): return max(Decimal("0"),Decimal(str(self.total or 0))-Decimal(str(self.paid or 0)))
    @property
    def status(self):
        if self.balance<=0:return "Paid"
        if self.due_date and self.due_date<date.today():return "Overdue"
        return "Due"

class Payment(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    invoice_id=db.Column(db.Integer,db.ForeignKey("invoice.id"),nullable=False)
    amount=db.Column(db.Numeric(12,2),nullable=False)
    method=db.Column(db.String(50),default="M-Pesa")
    reference=db.Column(db.String(100))
    paid_on=db.Column(db.Date,default=date.today)

class MpesaTransaction(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    invoice_id=db.Column(db.Integer,db.ForeignKey("invoice.id"),nullable=True)
    phone=db.Column(db.String(30),nullable=False)
    amount=db.Column(db.Numeric(12,2),nullable=False)
    checkout_id=db.Column(db.String(100),unique=True)
    merchant_request_id=db.Column(db.String(100))
    receipt=db.Column(db.String(100))
    status=db.Column(db.String(30),default="Pending")
    result_desc=db.Column(db.String(240))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    invoice=db.relationship("Invoice")

def auth(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get("admin"): return redirect(url_for("login"))
        return f(*a,**k)
    return w

def amount(v):
    x=Decimal(str(v))
    if x<0: raise ValueError
    return x.quantize(Decimal(".01"))

def wa_url(message):
    return "https://wa.me/"+WHATSAPP_NUMBER+"?text="+urllib.parse.quote(message)

def normalize_phone(p):
    p=(p or "").replace(" ","").replace("-","")
    if p.startswith("+254"): return p[1:]
    if p.startswith("254"): return p
    if p.startswith("07"): return "254"+p[1:]
    if p.startswith("01"): return "254"+p[1:]
    return p

def mpesa_token():
    key=os.getenv("MPESA_CONSUMER_KEY"); secret=os.getenv("MPESA_CONSUMER_SECRET")
    if not key or not secret: raise RuntimeError("M-Pesa credentials are not configured.")
    host="https://sandbox.safaricom.co.ke" if MPESA_ENV!="production" else "https://api.safaricom.co.ke"
    r=requests.get(host+"/oauth/v1/generate?grant_type=client_credentials",auth=(key,secret),timeout=20)
    r.raise_for_status(); return r.json()["access_token"]

def mpesa_stk(phone, amt, account):
    token=mpesa_token()
    passkey=os.getenv("MPESA_PASSKEY")
    if not passkey: raise RuntimeError("MPESA_PASSKEY is not configured.")
    shortcode=os.getenv("MPESA_SHORTCODE",MPESA_TILL)
    ts=datetime.now().strftime("%Y%m%d%H%M%S")
    password=base64.b64encode((shortcode+passkey+ts).encode()).decode()
    host="https://sandbox.safaricom.co.ke" if MPESA_ENV!="production" else "https://api.safaricom.co.ke"
    callback=(MPESA_CALLBACK_BASE or request.host_url.rstrip("/"))+"/mpesa/callback"
    payload={"BusinessShortCode":shortcode,"Password":password,"Timestamp":ts,
             "TransactionType":os.getenv("MPESA_TRANSACTION_TYPE","CustomerBuyGoodsOnline"),
             "Amount":int(Decimal(amt)),
             "PartyA":normalize_phone(phone),"PartyB":shortcode,"PhoneNumber":normalize_phone(phone),
             "CallBackURL":callback,"AccountReference":account[:12],"TransactionDesc":"Uranas Global payment"}
    r=requests.post(host+"/mpesa/stkpush/v1/processrequest",json=payload,headers={"Authorization":"Bearer "+token},timeout=30)
    r.raise_for_status(); return r.json()

def make_invoice_no():
    return "UG-"+datetime.now().strftime("%Y%m%d%H%M%S%f")[-10:]

def receipt_pdf(t):
    path=f"/tmp/uranas-receipt-{t.id}.pdf"
    doc=SimpleDocTemplate(path,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    styles=getSampleStyleSheet()
    title=ParagraphStyle("title",parent=styles["Title"],textColor=colors.HexColor("#075c43"))
    story=[Paragraph("URANAS GLOBAL",title),Paragraph("Hygiene today, healthier tomorrow.",styles["Normal"]),Spacer(1,10)]
    story += [Paragraph("PAYMENT RECEIPT",styles["Heading2"]),
              Paragraph(f"<b>Receipt:</b> {t.receipt or 'Pending'}",styles["Normal"]),
              Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d %B %Y, %H:%M')}",styles["Normal"]),
              Spacer(1,8)]
    inv=t.invoice
    data=[["Client",inv.client.name if inv else "Uranas Global Client"],
          ["Amount Paid",f"KSh {Decimal(str(t.amount)):,.2f}"],
          ["M-Pesa Receipt",t.receipt or "—"],
          ["Phone",t.phone]]
    if inv:
        data += [["Invoice",inv.invoice_no or f"#{inv.id}"],["Outstanding Balance",f"KSh {inv.balance:,.2f}"]]
    table=Table(data,colWidths=[45*mm,115*mm])
    table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.5,colors.HexColor("#dfe8e4")),
                               ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f1f7f4")),
                               ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
                               ("PADDING",(0,0),(-1,-1),7)]))
    story += [table,Spacer(1,20),Paragraph("Thank you for choosing Uranas Global.",styles["Normal"])]
    doc.build(story)
    return path

@app.route("/")
def home(): return render_template("home.html")

@app.route("/admin/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        pw=request.form.get("password",""); h=os.getenv("ADMIN_PASSWORD_HASH")
        ok=check_password_hash(h,pw) if h else pw==os.getenv("ADMIN_PASSWORD","")
        if ok: session["admin"]=True; return redirect(url_for("dashboard"))
        flash("Incorrect password.","error")
    return render_template("login.html")

@app.post("/admin/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/admin")
@auth
def dashboard():
    inv=Invoice.query.all()
    return render_template("dashboard.html",clients=Client.query.count(),
      billed=sum((Decimal(str(x.total)) for x in inv),Decimal()),
      paid=sum((Decimal(str(x.paid)) for x in inv),Decimal()),
      outstanding=sum((x.balance for x in inv),Decimal()),
      overdue=sum(x.status=="Overdue" for x in inv),
      recent=Invoice.query.order_by(Invoice.created_at.desc()).limit(8).all())

@app.route("/admin/clients")
@auth
def clients():
    q=request.args.get("q","").strip(); query=Client.query
    if q:
        s=f"%{q}%"; query=query.filter((Client.name.ilike(s))|(Client.phone.ilike(s))|(Client.email.ilike(s)))
    return render_template("clients.html",clients=query.order_by(Client.name).all(),q=q)

@app.route("/admin/clients/new",methods=["GET","POST"])
@auth
def new_client():
    if request.method=="POST":
        c=Client(name=request.form["name"].strip(),phone=request.form.get("phone"),email=request.form.get("email"),
                 service=request.form.get("service"),notes=request.form.get("notes"))
        db.session.add(c); db.session.commit(); flash("Client added.","success")
        return redirect(url_for("client",client_id=c.id))
    return render_template("client_form.html",client=None)

@app.route("/admin/clients/<int:client_id>")
@auth
def client(client_id): return render_template("client.html",client=db.get_or_404(Client,client_id))

@app.route("/admin/clients/<int:client_id>/edit",methods=["GET","POST"])
@auth
def edit_client(client_id):
    c=db.get_or_404(Client,client_id)
    if request.method=="POST":
        c.name=request.form["name"].strip(); c.phone=request.form.get("phone"); c.email=request.form.get("email")
        c.service=request.form.get("service"); c.notes=request.form.get("notes")
        db.session.commit(); flash("Client updated.","success"); return redirect(url_for("client",client_id=c.id))
    return render_template("client_form.html",client=c)

@app.post("/admin/clients/<int:client_id>/delete")
@auth
def delete_client(client_id):
    c=db.get_or_404(Client,client_id); db.session.delete(c); db.session.commit()
    flash("Client deleted.","success"); return redirect(url_for("clients"))

@app.post("/admin/clients/<int:client_id>/items")
@auth
def add_item(client_id):
    c=db.get_or_404(Client,client_id)
    try:
        item=ServiceItem(client_id=c.id,description=request.form["description"].strip(),
                         quantity=max(1,int(request.form["quantity"])),unit_price=amount(request.form["unit_price"]))
        db.session.add(item); db.session.commit(); flash("Service/bin item added.","success")
    except: flash("Enter valid item details.","error")
    return redirect(url_for("client",client_id=c.id))

@app.post("/admin/items/<int:item_id>/edit")
@auth
def edit_item(item_id):
    x=db.get_or_404(ServiceItem,item_id)
    try:
        x.description=request.form["description"].strip(); x.quantity=max(1,int(request.form["quantity"]))
        x.unit_price=amount(request.form["unit_price"]); x.active=request.form.get("active")=="on"
        db.session.commit(); flash("Item updated.","success")
    except: flash("Invalid item details.","error")
    return redirect(url_for("client",client_id=x.client_id))

@app.post("/admin/items/<int:item_id>/delete")
@auth
def delete_item(item_id):
    x=db.get_or_404(ServiceItem,item_id); cid=x.client_id; db.session.delete(x); db.session.commit()
    return redirect(url_for("client",client_id=cid))

@app.route("/admin/clients/<int:client_id>/invoice",methods=["GET","POST"])
@auth
def new_invoice(client_id):
    c=db.get_or_404(Client,client_id)
    if request.method=="POST":
        try:
            d=request.form.get("due_date"); due=datetime.strptime(d,"%Y-%m-%d").date() if d else None
            i=Invoice(client_id=c.id,invoice_no=make_invoice_no(),description=request.form["description"].strip(),
                      total=amount(request.form["total"]),due_date=due,period=request.form.get("period"))
            db.session.add(i); db.session.commit(); flash("Invoice/debt added.","success")
            return redirect(url_for("client",client_id=c.id))
        except: flash("Please enter valid invoice details.","error")
    return render_template("invoice_form.html",client=c)

@app.post("/admin/invoices/<int:invoice_id>/edit")
@auth
def edit_invoice(invoice_id):
    i=db.get_or_404(Invoice,invoice_id)
    try:
        i.description=request.form["description"].strip(); i.total=amount(request.form["total"])
        d=request.form.get("due_date"); i.due_date=datetime.strptime(d,"%Y-%m-%d").date() if d else None
        db.session.commit(); flash("Invoice updated.","success")
    except: flash("Invalid invoice details.","error")
    return redirect(url_for("client",client_id=i.client_id))

@app.post("/admin/invoices/<int:invoice_id>/payment")
@auth
def payment(invoice_id):
    i=db.get_or_404(Invoice,invoice_id)
    try:
        a=amount(request.form["amount"])
        if a<=0 or a>i.balance: raise ValueError
        i.paid=Decimal(str(i.paid))+a
        db.session.add(Payment(invoice_id=i.id,amount=a,method=request.form.get("method","M-Pesa"),reference=request.form.get("reference")))
        db.session.commit(); flash("Payment recorded.","success")
    except: flash("Payment is invalid or exceeds the balance.","error")
    return redirect(url_for("client",client_id=i.client_id))

@app.post("/admin/invoices/<int:invoice_id>/delete")
@auth
def delete_invoice(invoice_id):
    i=db.get_or_404(Invoice,invoice_id); cid=i.client_id; db.session.delete(i); db.session.commit()
    flash("Invoice deleted.","success"); return redirect(url_for("client",client_id=cid))

@app.get("/admin/clients/<int:client_id>/service-notification")
@auth
def service_notification(client_id):
    c=db.get_or_404(Client,client_id)
    return redirect(wa_url(f"""Hello {c.name},

This is a service notification from Uranas Global.

We are reaching out regarding your {c.service or 'service'} with us. Please contact us if you need to schedule, confirm, or make any changes.

Uranas Global
Hygiene today, healthier tomorrow.
WhatsApp: 0114685152"""))

@app.get("/admin/invoices/<int:invoice_id>/payment-notification")
@auth
def payment_notification(invoice_id):
    i=db.get_or_404(Invoice,invoice_id); c=i.client
    return redirect(wa_url(f"""Hello {c.name},

Thank you for choosing Uranas Global.

Payment update for {i.invoice_no or 'your invoice'}:
Total: KSh {float(i.total):,.2f}
Paid: KSh {float(i.paid):,.2f}
Outstanding balance: KSh {float(i.balance):,.2f}

Uranas Global
WhatsApp: 0114685152"""))

@app.get("/pay/<int:invoice_id>")
def pay_invoice(invoice_id):
    i=db.get_or_404(Invoice,invoice_id)
    return render_template("pay.html",invoice=i,till=MPESA_TILL)

@app.post("/pay/<int:invoice_id>/stk")
def request_stk(invoice_id):
    i=db.get_or_404(Invoice,invoice_id)
    try:
        a=amount(request.form["amount"]); phone=normalize_phone(request.form["phone"])
        if a<=0 or a>i.balance: raise ValueError("Invalid amount.")
        result=mpesa_stk(phone,a,i.invoice_no or f"INV{i.id}")
        t=MpesaTransaction(invoice_id=i.id,phone=phone,amount=a,checkout_id=result.get("CheckoutRequestID"),
                           merchant_request_id=result.get("MerchantRequestID"),status="Pending",
                           result_desc=result.get("ResponseDescription"))
        db.session.add(t); db.session.commit()
        return render_template("payment_wait.html",transaction=t,invoice=i)
    except Exception as e:
        flash(str(e),"error"); return redirect(url_for("pay_invoice",invoice_id=i.id))

@app.get("/payment-status/<int:tx_id>")
def payment_status(tx_id):
    t=db.get_or_404(MpesaTransaction,tx_id)
    return jsonify(status=t.status,receipt=t.receipt or "",description=t.result_desc or "",
                   receipt_url=url_for("receipt",tx_id=t.id) if t.status=="Completed" else "")

@app.post("/mpesa/callback")
def mpesa_callback():
    data=request.get_json(silent=True) or {}
    try:
        body=data.get("Body",{}).get("stkCallback",{})
        checkout=body.get("CheckoutRequestID"); t=MpesaTransaction.query.filter_by(checkout_id=checkout).first()
        if not t: return jsonify(ResultCode=0,ResultDesc="Accepted")
        code=body.get("ResultCode")
        if code==0:
            items={x.get("Name"):x.get("Value") for x in body.get("CallbackMetadata",{}).get("Item",[])}
            t.status="Completed"; t.receipt=items.get("MpesaReceiptNumber"); t.result_desc=body.get("ResultDesc")
            if t.invoice:
                t.invoice.paid=Decimal(str(t.invoice.paid))+Decimal(str(t.amount))
                db.session.add(Payment(invoice_id=t.invoice_id,amount=t.amount,method="M-Pesa",reference=t.receipt))
        else:
            t.status="Failed"; t.result_desc=body.get("ResultDesc")
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify(ResultCode=0,ResultDesc="Accepted")

@app.get("/receipt/<int:tx_id>")
def receipt(tx_id):
    t=db.get_or_404(MpesaTransaction,tx_id)
    if t.status!="Completed": return "Receipt is not ready yet.",409
    return send_file(receipt_pdf(t),as_attachment=False,download_name=f"Uranas-Receipt-{t.receipt}.pdf")

@app.get("/invoice/<int:invoice_id>.pdf")
def invoice_pdf(invoice_id):
    i=db.get_or_404(Invoice,invoice_id)
    path=f"/tmp/uranas-invoice-{i.id}.pdf"
    doc=SimpleDocTemplate(path,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    styles=getSampleStyleSheet(); title=ParagraphStyle("title",parent=styles["Title"],textColor=colors.HexColor("#075c43"))
    story=[Paragraph("URANAS GLOBAL",title),Paragraph("Hygiene today, healthier tomorrow.",styles["Normal"]),Spacer(1,8),
           Paragraph("INVOICE",styles["Heading1"]),Paragraph(f"<b>Invoice:</b> {i.invoice_no or i.id}",styles["Normal"]),
           Paragraph(f"<b>Date:</b> {i.created_at.strftime('%d %B %Y')}",styles["Normal"]),
           Paragraph(f"<b>Client:</b> {i.client.name}",styles["Normal"]),Spacer(1,10)]
    rows=[["Description","Amount"],[i.description,f"KSh {Decimal(str(i.total)):,.2f}"],["Paid",f"KSh {Decimal(str(i.paid)):,.2f}"],
          ["BALANCE",f"KSh {i.balance:,.2f}"]]
    table=Table(rows,colWidths=[105*mm,55*mm])
    table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.5,colors.HexColor("#dfe8e4")),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#075c43")),
                               ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
                               ("ALIGN",(1,0),(1,-1),"RIGHT"),("PADDING",(0,0),(-1,-1),7)]))
    story += [table,Spacer(1,12),Paragraph(f"Payment method: M-Pesa Till {MPESA_TILL}",styles["Normal"])]
    doc.build(story); return send_file(path,as_attachment=False,download_name=f"{i.invoice_no}.pdf")

def generate_monthly_invoices():
    today=date.today()
    if today.day!=30: return 0
    period=today.strftime("%Y-%m")
    made=0
    for c in Client.query.all():
        items=[x for x in c.items if x.active]
        if not items: continue
        if Invoice.query.filter_by(client_id=c.id,period=period).first(): continue
        total=sum((x.amount for x in items),Decimal())
        desc="Monthly service: "+"; ".join(f"{x.quantity} × {x.description} @ KSh {x.unit_price:,.2f}" for x in items)
        i=Invoice(client_id=c.id,invoice_no=make_invoice_no(),description=desc,total=total,
                  paid=Decimal("0"),due_date=today,period=period)
        db.session.add(i); made+=1
    db.session.commit(); return made

@app.get("/jobs/monthly-invoices")
def monthly_job():
    secret=os.getenv("CRON_SECRET")
    if secret and request.headers.get("X-Cron-Secret")!=secret: return "Unauthorized",401
    made=generate_monthly_invoices()
    return jsonify(created=made,date=str(date.today()))

with app.app_context(): db.create_all()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
