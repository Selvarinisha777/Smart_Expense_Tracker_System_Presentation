"""Smart Expense: Flask API, user-isolated ledger and responsive web client."""
import os, re, io, csv, secrets
from datetime import datetime, timedelta, date, timezone
from functools import wraps
from decimal import Decimal, InvalidOperation
import bcrypt, jwt
from flask import Flask, request, jsonify, render_template, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from intelligence import classify, parse_text, budget_summary, CATEGORIES

app = Flask(__name__)
app.config.update(SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///expense.db'), SQLALCHEMY_TRACK_MODIFICATIONS=False, MAX_CONTENT_LENGTH=8*1024*1024)
# Generate a private local key once; never ship keys with the source ZIP.
os.makedirs(app.instance_path, exist_ok=True)
key_path = os.path.join(app.instance_path, '.secret')
if not os.path.exists(key_path):
    with open(key_path, 'w') as f: f.write(secrets.token_hex(32))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or open(key_path).read().strip()
db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=False)
    income = db.Column(db.Numeric(12,2), default=0, nullable=False)
    version = db.Column(db.Integer, default=0, nullable=False)
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    merchant = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12,2), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(20), default='manual')
    def json(self):
        return dict(id=self.id,merchant=self.merchant,amount=float(self.amount),category=self.category,date=self.date.isoformat(),source=self.source)
with app.app_context(): db.create_all()

def fail(message, status=400): return jsonify(error=message), status
@app.errorhandler(413)
def too_large(e): return fail('Maximum upload size is 8 MB.',413)
@app.errorhandler(400)
def bad_request(e): return fail('Invalid request. Please check your input.')
@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

def private(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        try:
            token=request.headers.get('Authorization','').removeprefix('Bearer ')
            payload=jwt.decode(token,app.config['SECRET_KEY'],algorithms=['HS256'])
            user=db.session.get(User,int(payload['sub']))
            if not user or payload.get('v')!=user.version: raise ValueError()
        except (jwt.PyJWTError,ValueError,KeyError): return fail('Please sign in again.',401)
        return fn(user,*args,**kwargs)
    return wrapped

def money(value, allow_zero=False):
    try:
        d=Decimal(str(value))
        if not d.is_finite() or d < 0 or (not allow_zero and d==0) or d>Decimal('999999999'): raise ValueError()
        return d.quantize(Decimal('.01'))
    except (ValueError,InvalidOperation): raise ValueError('Enter a valid positive amount (maximum 999,999,999).')
def body(): return request.get_json(silent=True) or {}
@app.get('/')
def home(): return render_template('index.html')
@app.post('/api/auth/<action>')
def auth(action):
    data=body(); email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
    if len(email)>150 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): return fail('Enter a valid email address.')
    user=db.session.scalar(db.select(User).where(User.email==email))
    if action=='register':
        name=str(data.get('name','')).strip()
        if not name or len(name)>80: return fail('Enter your name (up to 80 characters).')
        if len(password)<8 or len(password.encode())>72: return fail('Use at least 8 characters, up to 72 UTF-8 bytes, for your password.')
        if user: return fail('This email already has an account.',409)
        try: income=money(data.get('income',0),True)
        except ValueError as e: return fail(str(e))
        user=User(name=name,email=email,password_hash=bcrypt.hashpw(password.encode(),bcrypt.gensalt()),income=income)
        db.session.add(user); db.session.commit()
    elif action=='login':
        if not user or len(password.encode())>72 or not bcrypt.checkpw(password.encode(),user.password_hash): return fail('Email or password is incorrect.',401)
    else: return fail('Unknown action.',404)
    token=jwt.encode({'sub':str(user.id),'v':user.version,'exp':datetime.now(timezone.utc)+timedelta(hours=8)},app.config['SECRET_KEY'],algorithm='HS256')
    return jsonify(token=token)
@app.post('/api/logout')
@private
def logout(user):
    user.version+=1; db.session.commit(); return jsonify(ok=True)
@app.get('/api/profile')
@private
def profile(user): return jsonify(name=user.name,email=user.email,income=float(user.income),categories=CATEGORIES)
@app.put('/api/profile')
@private
def update_profile(user):
    try: user.income=money(body().get('income'),True)
    except ValueError as e: return fail(str(e))
    db.session.commit(); return jsonify(ok=True)
def month_dates():
    month=request.args.get('month',date.today().strftime('%Y-%m'))
    start=datetime.strptime(month,'%Y-%m').date()
    end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    return start,end
@app.get('/api/transactions')
@private
def transactions(user):
    try: start,end=month_dates()
    except ValueError: return fail('Invalid month.')
    rows=db.session.scalars(db.select(Transaction).where(Transaction.user_id==user.id,Transaction.date>=start,Transaction.date<end).order_by(Transaction.date.desc(),Transaction.id.desc())).all()
    return jsonify([t.json() for t in rows])
@app.route('/api/transactions',methods=['POST'])
@app.route('/api/transactions/<int:tx_id>',methods=['PUT','DELETE'])
@private
def save_transaction(user,tx_id=None):
    tx=db.session.scalar(db.select(Transaction).where(Transaction.id==tx_id,Transaction.user_id==user.id)) if tx_id else None
    if tx_id and not tx: return fail('Transaction not found.',404)
    if request.method=='DELETE':
        db.session.delete(tx); db.session.commit(); return jsonify(ok=True)
    data=body()
    try:
        merchant=str(data.get('merchant','')).strip()
        if not merchant or len(merchant)>120: raise ValueError('Enter a description (up to 120 characters).')
        amount=money(data.get('amount')); dt=date.fromisoformat(str(data.get('date','')))
        category=data.get('category') or classify(merchant)['category']
        if category not in CATEGORIES: raise ValueError('Choose a valid category.')
        source=data.get('source','manual')
        if source not in ['manual','sms','receipt']: raise ValueError('Invalid transaction source.')
    except (ValueError,TypeError) as e: return fail(str(e) or 'Check transaction details.')
    if not tx: tx=Transaction(user_id=user.id); db.session.add(tx)
    tx.merchant=merchant; tx.amount=amount; tx.date=dt; tx.category=category; tx.source=source
    db.session.commit(); return jsonify(tx.json())
@app.get('/api/summary')
@private
def summary(user):
    try: start,end=month_dates()
    except ValueError: return fail('Invalid month.')
    rows=db.session.scalars(db.select(Transaction).where(Transaction.user_id==user.id,Transaction.date>=start,Transaction.date<end)).all()
    return jsonify(budget_summary(float(user.income),[x.json() for x in rows],start,end))
@app.post('/api/classify')
@private
def classification(user): return jsonify(classify(str(body().get('text',''))[:500]))
@app.post('/api/parse/sms')
@private
def sms(user):
    text=str(body().get('text',''))
    if not text.strip() or len(text)>10000: return fail('Paste an SMS message (up to 10,000 characters).')
    return jsonify(parse_text(text,'sms'))
@app.post('/api/parse/receipt')
@private
def receipt(user):
    f=request.files.get('file')
    if not f: return fail('Choose a receipt image.')
    try:
        from PIL import Image, ImageOps
        import pytesseract
        Image.MAX_IMAGE_PIXELS=16000000
        im=Image.open(f.stream); im.load()
        if im.width*im.height>16000000: return fail('Please upload an image smaller than 16 megapixels.')
        text=pytesseract.image_to_string(ImageOps.grayscale(ImageOps.exif_transpose(im)),timeout=20)
        if not text.strip(): return fail('No readable text found. Try a clearer photo.')
        return jsonify(parse_text(text,'receipt'))
    except Exception as e:
        if 'tesseract' in str(e).lower() and ('installed' in str(e).lower() or 'path' in str(e).lower()): return fail('Install Tesseract OCR and add it to PATH. See README.',503)
        return fail('Could not read this image. Use a clear JPG or PNG receipt.',422)
@app.get('/api/export')
@private
def export(user):
    out=io.StringIO(); writer=csv.writer(out); writer.writerow(['Date','Description','Category','Amount','Source'])
    rows=db.session.scalars(db.select(Transaction).where(Transaction.user_id==user.id).order_by(Transaction.date)).all()
    for t in rows:
        description=t.merchant
        if description.startswith(('=','+','-','@','\t','\r')): description="'"+description
        writer.writerow([t.date.isoformat(),description,t.category,str(t.amount),t.source])
    r=make_response(out.getvalue()); r.headers['Content-Type']='text/csv'; r.headers['Content-Disposition']='attachment; filename=expenses.csv'; return r
if __name__=='__main__': app.run(host='127.0.0.1',port=int(os.getenv('PORT',5000)),debug=False)
