import http.server
import os
import socketserver
import json
import hashlib
import html
import shutil
import secrets
from datetime import datetime, timezone
import urllib.request
import urllib.parse
from urllib.parse import parse_qs, urlparse
from http import cookies

# --- [ 1. الإعدادات والبيانات الأساسية ] ---
PORT = int(os.environ.get("PORT", 8080))
DB_FILE = os.path.join(os.path.dirname(__file__), "spider_master_database.json")
SITE_NAME = "SpiderSmm"
TELEGRAM_USER = "SmmSpider" 

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def h(value):
    return html.escape(str(value or ""), quote=True)

def money(value):
    return f"${float(value or 0):.2f}"

def make_referral_code(username):
    return f"{str(username).upper()[:8]}-{secrets.token_hex(2).upper()}"

def tier_for_user(db, username):
    spent = sum(float(o.get("cost", 0)) for o in db.get("orders", []) if o.get("user") == username)
    if spent >= 500:
        return "بلاتيني", 15
    if spent >= 200:
        return "ذهبي", 10
    if spent >= 50:
        return "فضي", 5
    return "برونزي", 0

def notify(db, username, title, message):
    db.setdefault("notifications", []).append({
        "id": secrets.token_hex(6), "user": username, "title": title,
        "message": message, "read": False, "created_at": now()
    })

def audit(db, actor, action, detail):
    db.setdefault("audit_logs", []).append({
        "actor": actor, "action": action, "detail": detail, "created_at": now()
    })

# --- [ 2. وظائف قاعدة البيانات ] ---
def load_db():
    if not os.path.exists(DB_FILE):
        data = {
            "users": {"admin": {
                "pass": hash_pass("nbel2712"), "balance": 0, "is_admin": True,
                "phone": "000", "email": "", "lang": "ar",
                "referral_code": "ADMIN-ROOT", "created_at": now()
            }},
            "services": [], 
            "orders": [], 
            "announcement": "مرحباً بك في عالم الفخامة الرقمية!",
            "is_active": True, "default_language": "ar",
            "topups": [], "coupons": [], "tickets": [],
            "notifications": [], "audit_logs": [], "referral_percent": 5
        }
        save_db(data)
        return data
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            backup = DB_FILE + ".corrupt"
            try:
                shutil.copy2(DB_FILE, backup)
            except Exception:
                pass
            return {
                "users": {}, "services": [], "orders": [], "topups": [],
                "coupons": [], "tickets": [], "notifications": [],
                "audit_logs": [], "announcement": "مرحباً بك في عالم الفخامة الرقمية!",
                "is_active": True, "default_language": "ar", "referral_percent": 5
            }

    changed = False
    data.setdefault("users", {})
    data.setdefault("services", [])
    data.setdefault("orders", [])
    data.setdefault("topups", [])
    data.setdefault("coupons", [])
    data.setdefault("tickets", [])
    data.setdefault("notifications", [])
    data.setdefault("audit_logs", [])
    data.setdefault("announcement", "مرحباً بك في عالم الفخامة الرقمية!")
    data.setdefault("is_active", True)
    data.setdefault("default_language", "ar")
    data.setdefault("referral_percent", 5)
    for username, account in data["users"].items():
        defaults = {
            "balance": 0.0, "is_admin": False, "phone": "", "email": "",
            "lang": "ar", "referral_code": make_referral_code(username),
            "created_at": now(), "referrals_earnings": 0.0
        }
        for key, value in defaults.items():
            if key not in account:
                account[key] = value
                changed = True
    if changed:
        save_db(data)
    return data

def save_db(data):
    temp_file = DB_FILE + ".tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(temp_file, DB_FILE)

# دالة إرسال الطلب للمزود تلقائياً
def send_api_order(api_url, api_key, service_id, link, quantity):
    try:
        params = {
            'key': api_key,
            'action': 'add',
            'service': service_id,
            'link': link,
            'quantity': quantity
        }
        query_string = urllib.parse.urlencode(params)
        full_url = f"{api_url}?{query_string}"
        
        with urllib.request.urlopen(full_url, timeout=10) as response:
            res_data = json.loads(response.read().decode())
            if "order" in res_data:
                return True, res_data["order"] # نجح الطلب ورجع رقم الطلب من المزود
            else:
                return False, res_data.get("error", "خطأ غير معروف من المزود")
    except Exception as e:
        return False, str(e)

def sync_api_order(api_url, api_key, remote_id):
    try:
        params = urllib.parse.urlencode({"key": api_key, "action": "status", "order": remote_id})
        with urllib.request.urlopen(f"{api_url}?{params}", timeout=10) as response:
            payload = json.loads(response.read().decode())
        status = str(payload.get("status", "")).lower()
        mapping = {
            "completed": "مكتمل", "complete": "مكتمل",
            "in progress": "قيد التنفيذ", "processing": "قيد التنفيذ",
            "pending": "معلّق", "canceled": "ملغى", "cancelled": "ملغى",
            "partial": "مكتمل جزئياً"
        }
        return True, mapping.get(status, payload.get("status", "قيد التنفيذ"))
    except Exception as e:
        return False, str(e)

# --- [ 3. التصميم المتكامل (UI/UX) ] ---
def get_master_style():
    return f"""
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        :root {{ --accent: #f39c12; --glass: rgba(255, 255, 255, 0.1); --border: rgba(255, 255, 255, 0.15); }}
        * {{ box-sizing: border-box; font-family: 'Cairo', sans-serif; transition: 0.3s; }}
        body {{ 
            margin: 0; background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); 
            background-attachment: fixed; color: #fff; direction: rtl; padding-bottom: 120px; min-height: 100vh;
        }}
        .header {{ 
            height: 75px; background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            display: flex; align-items: center; justify-content: space-between; 
            padding: 0 20px; border-bottom: 1px solid var(--border); position: sticky; top:0; z-index:1000; 
        }}
        .card {{ 
            background: var(--glass); border: 1px solid var(--border); border-radius: 28px; 
            padding: 22px; margin: 15px; backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }}
        .settings-group {{ margin-bottom: 20px; }}
        .settings-title {{ font-size: 14px; color: var(--accent); margin: 0 15px 10px; font-weight: bold; opacity: 0.8; }}
        .settings-list {{ background: rgba(255,255,255,0.03); border-radius: 20px; overflow: hidden; border: 1px solid var(--border); margin: 0 15px; }}
        .settings-item {{ 
            display: flex; align-items: center; padding: 18px; text-decoration: none; 
            color: #fff; border-bottom: 1px solid var(--border); 
        }}
        .settings-item:last-child {{ border: none; }}
        .settings-item:active {{ background: rgba(255,255,255,0.1); }}
        .settings-item i {{ width: 35px; font-size: 20px; color: var(--accent); }}
        .settings-item .text {{ flex: 1; font-size: 15px; font-weight: 500; }}
        .settings-item .chevron {{ font-size: 12px; opacity: 0.3; }}
        input, select, button {{ 
            width: 100%; padding: 18px; margin-top: 15px; border-radius: 20px; 
            border: 1px solid var(--border); background: rgba(255, 255, 255, 0.05); color: #fff; outline: none;
            font-size: 16px; font-weight: bold;
        }}
        .btn-send {{ 
            background: linear-gradient(45deg, var(--accent), #e67e22); 
            color: #000; font-weight: 900; border: none; cursor: pointer;
            box-shadow: 0 6px 20px rgba(243, 156, 18, 0.4);
        }}
        .floating-tg {{
            position: fixed; bottom: 125px; left: 25px; width: 65px; height: 65px;
            background: linear-gradient(45deg, #0088cc, #00aaff); border-radius: 50%; 
            display: flex; align-items: center; justify-content: center; color: white; 
            font-size: 32px; z-index: 3000; box-shadow: 0 8px 25px rgba(0,136,204,0.5); 
            text-decoration: none; animation: pulse 2s infinite;
        }}
        @keyframes pulse {{ 0% {{ transform: scale(1); }} 50% {{ transform: scale(1.08); }} 100% {{ transform: scale(1); }} }}
        .bottom-nav {{ 
            position: fixed; bottom: 25px; left: 20px; right: 20px; 
            height: 85px; background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(25px);
            display: flex; justify-content: space-around; align-items: center; 
            border-radius: 35px; border: 1px solid var(--border); z-index: 2000;
        }}
        .nav-item {{ color: rgba(255,255,255,0.4); text-decoration: none; font-size: 13px; text-align: center; flex:1; }}
        .nav-item.active {{ color: var(--accent); text-shadow: 0 0 10px var(--accent); }}
        .nav-item i {{ font-size: 28px; display: block; margin-bottom: 5px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 0 15px; }}
        .stat-item {{ background: var(--glass); border: 1px solid var(--border); border-radius: 20px; padding: 15px; text-align: center; }}
        .stat-item i {{ color: var(--accent); display: block; margin-bottom: 8px; font-size: 22px; }}
        .stat-label {{ font-size: 11px; color: rgba(255,255,255,0.6); }}
        .stat-value {{ font-size: 16px; font-weight: bold; }}
        .badge {{ background: var(--accent); color: #000; padding: 4px 12px; border-radius: 12px; font-weight: bold; font-size: 13px; }}
        .order-row {{ border-bottom: 1px solid var(--border); padding: 18px 0; display: flex; justify-content: space-between; align-items: center; }}
    </style>
    <a href="https://t.me/{TELEGRAM_USER}" class="floating-tg" target="_blank"><i class="fab fa-telegram-plane"></i></a>
    """

# --- [ 4. الواجهات ] ---
def get_welcome_page(error=""):
    return f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <meta name="theme-color" content="#07101f">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap');
            :root {{
                --bg: #060b16; --panel: rgba(12, 21, 38, .78); --line: rgba(255,255,255,.1);
                --muted: #91a0b8; --gold: #ffc857; --orange: #ff8a3d; --cyan: #54d7ff;
                --green: #61e6a1; --danger: #ff6b7a;
            }}
            * {{ box-sizing: border-box; font-family: 'Cairo', sans-serif; }}
            html, body {{ min-height:100%; margin:0; background:var(--bg); color:#fff; overflow-x:hidden; }}
            body {{ position:relative; }}
            body::before {{ content:""; position:fixed; inset:0; pointer-events:none; opacity:.2;
                background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
                background-size:52px 52px; mask-image:linear-gradient(to bottom, black, transparent 80%); }}
            .orb {{ position:fixed; border-radius:50%; filter:blur(10px); pointer-events:none; opacity:.4; }}
            .orb-one {{ width:380px; height:380px; background:#104a77; top:-170px; right:-100px; }}
            .orb-two {{ width:310px; height:310px; background:#723e17; bottom:-130px; left:-100px; }}
            .page {{ width:min(1200px, 100%); min-height:100vh; margin:auto; padding:32px;
                display:grid; grid-template-columns:1.12fr .88fr; gap:70px; align-items:center; position:relative; }}
            .brand {{ display:flex; align-items:center; gap:12px; font-weight:900; letter-spacing:-.5px; }}
            .brand-mark {{ width:48px; height:48px; border-radius:16px; display:grid; place-items:center;
                color:#111; background:linear-gradient(135deg,var(--gold),var(--orange));
                box-shadow:0 0 30px rgba(255,200,87,.3); font-size:25px; transform:rotate(-8deg); }}
            .brand span {{ font-size:21px; }} .brand small {{ display:block; color:var(--muted); font-size:10px; font-weight:500; letter-spacing:1px; }}
            .hero {{ padding:10px 0; }}
            .live-pill {{ display:inline-flex; align-items:center; gap:9px; color:var(--green); border:1px solid rgba(97,230,161,.22);
                background:rgba(97,230,161,.07); border-radius:99px; padding:7px 13px; font-size:11px; font-weight:700; }}
            .live-dot {{ width:7px; height:7px; background:var(--green); border-radius:50%; box-shadow:0 0 0 5px rgba(97,230,161,.1); }}
            .hero h1 {{ max-width:630px; margin:26px 0 16px; font-size:clamp(38px, 5vw, 70px); line-height:1.14; letter-spacing:-2px; }}
            .hero h1 .gradient {{ background:linear-gradient(100deg,var(--gold),#fff 55%,var(--cyan)); -webkit-background-clip:text; background-clip:text; color:transparent; }}
            .hero-copy {{ max-width:535px; color:var(--muted); font-size:16px; line-height:2; }}
            .hero-copy b {{ color:#e8eef8; }}
            .feature-grid {{ margin-top:34px; display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; max-width:600px; }}
            .feature {{ border:1px solid var(--line); background:rgba(255,255,255,.035); border-radius:20px; padding:17px 15px; }}
            .feature i {{ color:var(--gold); font-size:18px; margin-bottom:11px; }}
            .feature b {{ display:block; font-size:13px; }} .feature span {{ color:var(--muted); font-size:10px; }}
            .stats {{ display:flex; gap:28px; margin-top:34px; color:var(--muted); font-size:11px; }}
            .stats strong {{ display:block; color:#fff; font-size:21px; line-height:1.25; }}
            .auth-wrap {{ width:100%; max-width:440px; justify-self:end; }}
            .auth-card {{ background:linear-gradient(145deg,rgba(18,31,53,.9),rgba(7,13,26,.86)); border:1px solid var(--line);
                border-radius:30px; padding:28px; box-shadow:0 30px 90px rgba(0,0,0,.45), inset 0 1px rgba(255,255,255,.05);
                backdrop-filter:blur(25px); }}
            .card-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:22px; }}
            .card-head h2 {{ margin:0; font-size:22px; }} .card-head p {{ margin:4px 0 0; color:var(--muted); font-size:11px; }}
            .secure {{ color:var(--green); font-size:10px; display:flex; gap:5px; align-items:center; }}
            .tabs {{ display:grid; grid-template-columns:1fr 1fr; gap:4px; padding:4px; background:rgba(0,0,0,.25); border-radius:15px; margin-bottom:22px; }}
            .tab {{ border:0; background:transparent; color:var(--muted); border-radius:11px; padding:11px; cursor:pointer; font-size:12px; font-weight:700; }}
            .tab.active {{ color:#111; background:linear-gradient(135deg,var(--gold),var(--orange)); }}
            .form-panel[hidden] {{ display:none; }}
            .field {{ position:relative; margin-bottom:14px; }} .field > i {{ position:absolute; right:16px; top:17px; color:#6f819d; font-size:14px; }}
            .field input {{ width:100%; height:52px; padding:0 45px 0 45px; color:#fff; background:rgba(0,0,0,.2);
                border:1px solid rgba(255,255,255,.1); border-radius:15px; outline:none; font-size:13px; }}
            .field input::placeholder {{ color:#64738b; }} .field input:focus {{ border-color:rgba(255,200,87,.75); box-shadow:0 0 0 4px rgba(255,200,87,.08); }}
            .password-toggle {{ position:absolute; left:10px; top:10px; border:0; background:transparent; color:#718199; cursor:pointer; width:32px; height:32px; }}
            .action {{ width:100%; height:54px; border:0; border-radius:16px; cursor:pointer; color:#111; font-weight:900; font-size:15px;
                background:linear-gradient(110deg,var(--gold),var(--orange)); box-shadow:0 13px 30px rgba(255,138,61,.22); margin-top:4px; }}
            .action:hover {{ transform:translateY(-2px); box-shadow:0 16px 35px rgba(255,138,61,.32); }}
            .forgot {{ display:block; color:var(--gold); text-align:left; font-size:11px; text-decoration:none; margin:3px 2px 19px; }}
            .error {{ color:var(--danger); background:rgba(255,107,122,.09); border:1px solid rgba(255,107,122,.2); padding:10px 12px; border-radius:12px; font-size:11px; margin-bottom:15px; }}
            .switch {{ color:var(--muted); text-align:center; font-size:11px; margin-top:18px; }} .switch button {{ color:var(--gold); background:none; border:0; cursor:pointer; font-weight:800; }}
            .strength {{ display:flex; align-items:center; gap:8px; margin:-6px 2px 12px; color:var(--muted); font-size:10px; }}
            .strength-bar {{ height:4px; flex:1; border-radius:4px; background:#273348; overflow:hidden; }} .strength-bar i {{ display:block; height:100%; width:0; transition:.3s; background:var(--danger); }}
            .terms {{ color:#687791; font-size:10px; line-height:1.8; margin-top:15px; text-align:center; }} .terms a {{ color:#aab8cc; }}
            .trust {{ display:flex; align-items:center; justify-content:center; gap:8px; color:#7c8da7; font-size:10px; margin-top:19px; }}
            .trust i {{ color:var(--green); }} @media (max-width:880px) {{
                .page {{ grid-template-columns:1fr; gap:28px; padding:22px 16px 40px; align-items:start; }}
                .hero {{ text-align:center; order:2; }} .auth-wrap {{ order:1; justify-self:center; }}
                .brand {{ justify-content:center; }} .hero h1 {{ font-size:42px; margin-top:22px; }}
                .hero-copy {{ margin:auto; font-size:13px; }} .feature-grid {{ margin:25px auto 0; }} .stats {{ justify-content:center; }}
            }} @media (max-width:480px) {{
                .page {{ padding:15px 12px 35px; }} .auth-card {{ padding:20px 16px; border-radius:24px; }}
                .hero h1 {{ font-size:35px; letter-spacing:-1px; }} .feature-grid {{ gap:8px; }}
                .feature {{ padding:13px 9px; }} .feature b {{ font-size:11px; }} .feature span {{ font-size:9px; }}
                .stats {{ gap:18px; }} .stats strong {{ font-size:18px; }}
            }} @media (prefers-reduced-motion:reduce) {{ *, *::before, *::after {{ animation:none!important; transition:none!important; }} }}
        </style>
    </head>
    <body>
        <div class="orb orb-one"></div><div class="orb orb-two"></div>
        <main class="page">
            <section class="hero">
                <div class="brand"><div class="brand-mark"><i class="fas fa-spider"></i></div><div><span>{SITE_NAME}</span><small>SMART SOCIAL GROWTH</small></div></div>
                <div style="margin-top:45px;" class="live-pill"><i class="live-dot"></i> المنصة تعمل الآن · خدمة فورية</div>
                <h1>خلّي حضورك الرقمي<br><span class="gradient">يتكلم عنك.</span></h1>
                <p class="hero-copy">كل أدوات النمو التي تحتاجها في مكان واحد. اطلب خدمتك خلال ثوانٍ، تابع التنفيذ مباشرة، وخلّ تركيزك على <b>صناعة محتوى أقوى.</b></p>
                <div class="feature-grid">
                    <div class="feature"><i class="fas fa-bolt"></i><b>تنفيذ سريع</b><span>بدء تلقائي للطلبات</span></div>
                    <div class="feature"><i class="fas fa-chart-line"></i><b>نتائج واضحة</b><span>تتبع لحظي لحملاتك</span></div>
                    <div class="feature"><i class="fas fa-shield-halved"></i><b>خصوصية تامة</b><span>بياناتك في أمان</span></div>
                </div>
                <div class="stats"><div><strong>24/7</strong>دعم مستمر</div><div><strong>99%</strong>رضا العملاء</div><div><strong>1M+</strong>طلب ناجح</div></div>
            </section>
            <section class="auth-wrap">
                <div class="auth-card">
                    <div class="card-head"><div><h2 id="auth-title">مرحباً بعودتك</h2><p id="auth-subtitle">سجّل دخولك لإدارة نموك</p></div><div class="secure"><i class="fas fa-lock"></i> اتصال آمن</div></div>
                    <div class="tabs"><button class="tab active" id="login-tab" onclick="showAuth('login')">تسجيل الدخول</button><button class="tab" id="register-tab" onclick="showAuth('register')">عضوية جديدة</button></div>
                    {f'<div class="error"><i class="fas fa-circle-exclamation"></i> {h(error)}</div>' if error else ''}
                    <div id="login-form" class="form-panel">
                        <form action="/auth" method="GET">
                            <div class="field"><i class="fas fa-user"></i><input type="text" name="user" placeholder="اسم المستخدم" autocomplete="username" required></div>
                            <div class="field"><i class="fas fa-lock"></i><input id="login-pass" type="password" name="pass" placeholder="كلمة المرور" autocomplete="current-password" required><button type="button" class="password-toggle" aria-label="إظهار كلمة المرور" onclick="togglePassword('login-pass', this)"><i class="fas fa-eye"></i></button></div>
                            <a class="forgot" href="/forgot_password">نسيت كلمة المرور؟</a>
                            <button class="action" type="submit"><i class="fas fa-arrow-left"></i> دخول آمن إلى حسابي</button>
                        </form>
                        <div class="switch">جديد هنا؟ <button type="button" onclick="showAuth('register')">أنشئ حسابك خلال دقيقة</button></div>
                    </div>
                    <div id="register-form" class="form-panel" hidden>
                        <form action="/register" method="GET">
                            <div class="field"><i class="fas fa-user-plus"></i><input type="text" name="nu" placeholder="اختر اسم مستخدم" autocomplete="username" pattern="[A-Za-z0-9_-]+" required></div>
                            <div class="field"><i class="fas fa-key"></i><input id="register-pass" type="password" name="np" placeholder="أنشئ كلمة مرور قوية" autocomplete="new-password" minlength="6" required oninput="passwordStrength(this.value)"><button type="button" class="password-toggle" aria-label="إظهار كلمة المرور" onclick="togglePassword('register-pass', this)"><i class="fas fa-eye"></i></button></div>
                            <div class="strength"><span id="strength-label">قوة كلمة المرور</span><div class="strength-bar"><i id="strength-fill"></i></div></div>
                            <div class="field"><i class="fas fa-phone"></i><input type="tel" name="ph" placeholder="رقم الهاتف للتواصل" autocomplete="tel" required></div>
                            <div class="field"><i class="fas fa-user-group"></i><input type="text" name="ref" placeholder="كود الإحالة (اختياري)"></div>
                            <button class="action" type="submit"><i class="fas fa-sparkles"></i> ابدأ رحلتك الآن</button>
                        </form>
                        <div class="switch">لديك حساب بالفعل؟ <button type="button" onclick="showAuth('login')">سجّل دخولك</button></div>
                    </div>
                    <div class="terms">بالمتابعة، أنت توافق على <a href="/terms">شروط الاستخدام</a> وسياسة الخصوصية الخاصة بالمنصة.</div>
                    <div class="trust"><i class="fas fa-circle-check"></i> لا نطلب كلمة مرور حساباتك الاجتماعية · الدفع الآمن قريباً</div>
                </div>
            </section>
        </main>
        <script>
            function showAuth(mode) {{
                const login = mode === 'login';
                document.getElementById('login-form').hidden = !login;
                document.getElementById('register-form').hidden = login;
                document.getElementById('login-tab').classList.toggle('active', login);
                document.getElementById('register-tab').classList.toggle('active', !login);
                document.getElementById('auth-title').textContent = login ? 'مرحباً بعودتك' : 'ابدأ عضويتك';
                document.getElementById('auth-subtitle').textContent = login ? 'سجّل دخولك لإدارة نموك' : 'كل شيء جاهز لنمو حسابك';
            }}
            function togglePassword(id, button) {{
                const input = document.getElementById(id), icon = button.querySelector('i');
                input.type = input.type === 'password' ? 'text' : 'password';
                icon.classList.toggle('fa-eye'); icon.classList.toggle('fa-eye-slash');
            }}
            function passwordStrength(value) {{
                const fill = document.getElementById('strength-fill'), label = document.getElementById('strength-label');
                let score = 0; if (value.length >= 6) score++; if (value.length >= 10) score++;
                if (/[A-Z]/.test(value) && /[0-9]/.test(value)) score++; if (/[^A-Za-z0-9]/.test(value)) score++;
                const widths = ['0%', '25%', '50%', '75%', '100%'], colors = ['#273348','#ff6b7a','#ffb454','#8bdc91','#61e6a1'];
                fill.style.width = widths[score]; fill.style.background = colors[score];
                label.textContent = score < 2 ? 'كلمة مرور ضعيفة' : (score < 4 ? 'كلمة مرور جيدة' : 'كلمة مرور قوية');
            }}
        </script>
    </body>
    </html>
    """
    
def get_forgot_password_page(message=""):
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">استرجاع كلمة المرور</b><a href="/" style="color:white;font-size:24px;"><i class="fas fa-arrow-right"></i></a></div>
    <div class="card"><p style="opacity:.7;">استخدم اسم المستخدم ورقم الهاتف المسجل لإنشاء كلمة مرور جديدة.</p>{f'<p style="color:#2ecc71;">{h(message)}</p>' if message else ''}
    <form action="/forgot_action" method="GET"><input name="user" placeholder="اسم المستخدم" required><input name="phone" placeholder="رقم الهاتف" required><input type="password" name="new" placeholder="كلمة المرور الجديدة" minlength="6" required><button class="btn-send">تحديث كلمة المرور</button></form></div>
    </body></html>"""


def get_orders_page(db, user):
    orders = [o for o in db.get("orders", []) if o.get('user') == user]
    orders_html = ""
    for o in reversed(orders):
        status = str(o.get('status', ''))
        status_color = "#2ecc71" if "مكتمل" in status else ("#ff6b7a" if "ملغى" in status else "#f39c12")
        orders_html += f"""
        <div class="order-row order-card" data-service="{h(o.get('svc'))}" data-status="{h(status)}">
            <div>
                <div style="font-weight:bold;">{h(o.get('svc'))}</div>
                <div style="font-size:12px; opacity:0.6;">الكمية: {h(o.get('qty'))} | التكلفة: {money(o.get('cost'))}</div>
                <div style="font-size:11px; opacity:0.45;">{h(o.get('created_at', ''))}</div>
            </div>
            <div style="color:{status_color}; font-weight:bold; font-size:14px;">{h(status)}</div>
        </div>"""
    if not orders_html:
        orders_html = "<p style='text-align:center; opacity:0.5; margin-top:50px;'>ليس لديك طلبات سابقة</p>"
    return f"""<!DOCTYPE html><html lang="ar"><head><meta charset="UTF-8">{get_master_style()}</head><body>
        <div class="header"><div style="font-weight:900; color:var(--accent); font-size:22px;">سجل طلباتي</div><a href="/" style="color:white; font-size:24px;"><i class="fas fa-home"></i></a></div>
        <div class="card">
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px;">
                <input id="order-search" type="search" placeholder="ابحث باسم الخدمة..." oninput="filterOrders()" style="flex:1;min-width:190px;margin:0;">
                <select id="order-status" onchange="filterOrders()" style="width:auto;min-width:135px;margin:0;"><option value="">كل الحالات</option><option>مكتمل</option><option>قيد التنفيذ</option><option>معلّق</option><option>ملغى</option></select>
            </div>
            <p id="orders-empty" style="display:none;text-align:center;opacity:.55;">لا توجد نتائج مطابقة</p>
            <div id="orders-list">{orders_html}</div>
        </div>
        <div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/topup" class="nav-item"><i class="fas fa-wallet"></i>الرصيد</a><a href="/settings" class="nav-item"><i class="fas fa-cog"></i>الإعدادات</a></div>
        <script>
        function filterOrders() {{
            const query = document.getElementById('order-search').value.toLowerCase();
            const status = document.getElementById('order-status').value;
            let visible = 0;
            document.querySelectorAll('.order-card').forEach(card => {{
                const match = card.dataset.service.toLowerCase().includes(query) && (!status || card.dataset.status.includes(status));
                card.style.display = match ? 'flex' : 'none'; if (match) visible++;
            }});
            document.getElementById('orders-empty').style.display = visible ? 'none' : 'block';
        }}
        </script>
    </body></html>"""

def get_settings_page(db, user):
    u = db["users"][user]
    level, discount = tier_for_user(db, user)
    unread = len([n for n in db.get("notifications", []) if n.get("user") == user and not n.get("read")])
    admin_item = f"""<a href="/admin_panel" class="settings-item"><i class="fas fa-user-shield"></i><span class="text">لوحة التحكم للإدارة</span><i class="fas fa-chevron-left chevron"></i></a>""" if u.get('is_admin') else ""
    return f"""<!DOCTYPE html><html lang="ar"><head><meta charset="UTF-8">{get_master_style()}</head><body>
        <div class="header"><div style="font-weight:900; color:var(--accent); font-size:22px;">{SITE_NAME}</div><a href="/" style="color:white; font-size:24px;"><i class="fas fa-times"></i></a></div>
        <div class="card" style="text-align:center;">
            <div style="width:80px; height:80px; background:rgba(243,156,18,0.1); border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 15px; border:1px solid var(--accent);"><i class="fas fa-user" style="font-size:35px; color:var(--accent);"></i></div>
            <h2 style="margin:0;">{h(user)}</h2><div class="badge" style="margin-top:10px;">الرصيد: {money(u.get('balance'))}</div>
            <div style="margin-top:12px; opacity:.75;">المستوى: <b>{level}</b> · خصمك الحالي: {discount}%</div>
        </div>
        <div class="settings-group">
            <div class="settings-title">الحساب والمالية</div>
            <div class="settings-list">
                <a href="/order_history" class="settings-item"><i class="fas fa-history"></i><span class="text">سجل طلباتي</span><i class="fas fa-chevron-left chevron"></i></a>
                <a href="/topup" class="settings-item"><i class="fas fa-wallet"></i><span class="text">شحن الرصيد</span><i class="fas fa-chevron-left chevron"></i></a>
                <a href="/referrals" class="settings-item"><i class="fas fa-user-plus"></i><span class="text">الإحالات والأرباح</span><i class="fas fa-chevron-left chevron"></i></a>
                <a href="/notifications" class="settings-item"><i class="fas fa-bell"></i><span class="text">الإشعارات ({unread})</span><i class="fas fa-chevron-left chevron"></i></a>
                <a href="/change_password" class="settings-item"><i class="fas fa-lock"></i><span class="text">تغيير كلمة المرور</span><i class="fas fa-chevron-left chevron"></i></a>
                {admin_item}
            </div>
        </div>
        <div class="settings-group"><div class="settings-title">الدعم والمعلومات</div><div class="settings-list">
            <a href="/support" class="settings-item"><i class="fas fa-headset"></i><span class="text">تذاكر الدعم الفني</span><i class="fas fa-chevron-left chevron"></i></a>
            <a href="https://t.me/{TELEGRAM_USER}" target="_blank" class="settings-item"><i class="fab fa-telegram-plane"></i><span class="text">قناتنا على التليجرام</span><i class="fas fa-chevron-left chevron"></i></a>
            <a href="/terms" class="settings-item"><i class="fas fa-info-circle"></i><span class="text">شروط الاستخدام</span><i class="fas fa-chevron-left chevron"></i></a>
        </div></div>
        <div class="settings-group" style="margin-bottom:120px;"><div class="settings-list"><a href="/logout" class="settings-item" style="color:#ff4757;"><i class="fas fa-sign-out-alt" style="color:#ff4757;"></i><span class="text">تسجيل الخروج</span></a></div></div>
        <div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/topup" class="nav-item"><i class="fas fa-wallet"></i>الرصيد</a><a href="/support" class="nav-item"><i class="fas fa-headset"></i>الدعم</a></div>
    </body></html>"""

def get_topup_page(db, user, message=""):
    u = db["users"][user]
    topups = [t for t in db.get("topups", []) if t.get("user") == user]
    rows = "".join(
        f"""<div class="order-row"><div><b>{money(t.get('amount'))}</b><br><small>{h(t.get('method'))} · {h(t.get('created_at'))}</small></div>
        <span class="badge" style="background:{'#2ecc71' if t.get('status') == 'مقبول' else '#f39c12'}">{h(t.get('status'))}</span></div>"""
        for t in reversed(topups)
    ) or "<p style='opacity:.55;text-align:center;'>لا توجد طلبات شحن بعد</p>"
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">شحن الرصيد</b><a href="/" style="color:white;font-size:24px;"><i class="fas fa-home"></i></a></div>
    <div class="card"><h3 style="color:var(--accent);">رصيدك الحالي: {money(u.get('balance'))}</h3>
    {f'<div class="card" style="margin:0 0 15px;color:#2ecc71;">{h(message)}</div>' if message else ''}
    <form action="/topup_action" method="GET">
      <input type="hidden" name="type" value="request">
      <input type="number" step="0.01" min="1" name="amount" placeholder="المبلغ المطلوب" required>
      <select name="method" required><option value="">اختر طريقة الدفع</option><option>تحويل بنكي</option><option>محفظة إلكترونية</option><option>بطاقة شحن</option></select>
      <input name="reference" placeholder="رقم العملية أو ملاحظة الدفع" required>
      <button class="btn-send">إرسال طلب الشحن</button>
    </form>
    </div><div class="card"><h3 style="color:var(--accent);">طلبات الشحن السابقة</h3>{rows}</div>
    <div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/order_history" class="nav-item"><i class="fas fa-history"></i>الطلبات</a><a href="/settings" class="nav-item"><i class="fas fa-cog"></i>الإعدادات</a></div>
    </body></html>"""

def get_notifications_page(db, user):
    notes = [n for n in db.get("notifications", []) if n.get("user") == user]
    rows = "".join(
        f"""<div class="order-row"><div><b>{h(n.get('title'))}</b><br><span style="opacity:.72;">{h(n.get('message'))}</span><br><small>{h(n.get('created_at'))}</small></div>
        <span style="color:{'#2ecc71' if n.get('read') else 'var(--accent)'}">{'مقروء' if n.get('read') else 'جديد'}</span></div>"""
        for n in reversed(notes)
    ) or "<p style='opacity:.55;text-align:center;'>لا توجد إشعارات</p>"
    for n in notes:
        n["read"] = True
    save_db(db)
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">الإشعارات</b><a href="/" style="color:white;font-size:24px;"><i class="fas fa-home"></i></a></div>
    <div class="card">{rows}</div><div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/settings" class="nav-item"><i class="fas fa-cog"></i>الإعدادات</a></div>
    </body></html>"""

def get_referrals_page(db, user):
    u = db["users"][user]
    referred = [name for name, account in db.get("users", {}).items() if account.get("referred_by") == user]
    earnings = float(u.get("referrals_earnings", 0))
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">برنامج الإحالة</b><a href="/" style="color:white;font-size:24px;"><i class="fas fa-home"></i></a></div>
    <div class="card" style="text-align:center;"><i class="fas fa-users" style="font-size:48px;color:var(--accent);"></i><h2>ادعُ أصدقاءك واربح</h2>
      <p style="opacity:.7;">تحصل على نسبة من أول شحن للأعضاء عن طريقك.</p>
       <div style="display:flex;gap:8px;align-items:stretch;"><div id="ref-code" style="flex:1;padding:15px;background:rgba(243,156,18,.12);border:1px dashed var(--accent);border-radius:16px;font-size:20px;font-weight:bold;">{h(u.get('referral_code'))}</div><button onclick="copyReferral()" style="width:54px;margin:0;border-radius:16px;background:var(--accent);color:#000;border:0;cursor:pointer;" title="نسخ الكود"><i class="fas fa-copy"></i></button></div>
       <p id="copy-state" style="height:18px;color:#2ecc71;font-size:12px;margin:8px 0 0;"></p>
      <p>إجمالي أرباح الإحالات: <b style="color:#2ecc71;">{money(earnings)}</b></p><p>عدد الإحالات: <b>{len(referred)}</b></p>
       <button onclick="shareReferral()" class="btn-send" style="margin-top:4px;"><i class="fas fa-share-nodes"></i> مشاركة كود الإحالة</button>
     </div><div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/settings" class="nav-item"><i class="fas fa-cog"></i>الإعدادات</a></div>
     <script>
     function copyReferral() {{
         navigator.clipboard.writeText(document.getElementById('ref-code').textContent.trim()).then(() => document.getElementById('copy-state').textContent = 'تم نسخ الكود بنجاح');
     }}
     function shareReferral() {{
         const code = document.getElementById('ref-code').textContent.trim(), text = 'انضم إلى {SITE_NAME} باستخدام كود الإحالة: ' + code;
         if (navigator.share) navigator.share({{title:'{SITE_NAME}', text:text}}); else {{ copyReferral(); document.getElementById('copy-state').textContent = 'تم نسخ نص المشاركة'; }}
     }}
     </script>
    </body></html>"""

def get_change_password_page(message=""):
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">تغيير كلمة المرور</b><a href="/settings" style="color:white;font-size:24px;"><i class="fas fa-arrow-right"></i></a></div>
    <div class="card">{f'<p style="color:#2ecc71;">{h(message)}</p>' if message else ''}
    <form action="/change_password_action" method="GET"><input type="password" name="old" placeholder="كلمة المرور الحالية" required><input type="password" name="new" placeholder="كلمة المرور الجديدة" minlength="6" required><input type="password" name="confirm" placeholder="تأكيد كلمة المرور" minlength="6" required><button class="btn-send">حفظ كلمة المرور</button></form></div>
    </body></html>"""

def get_support_page(db, user, message=""):
    tickets = [t for t in db.get("tickets", []) if t.get("user") == user]
    rows = "".join(f"""<div class="order-row"><div><b>#{h(t.get('id'))} · {h(t.get('subject'))}</b><br><small>{h(t.get('created_at'))}</small></div><span class="badge">{h(t.get('status'))}</span></div>""" for t in reversed(tickets)) or "<p style='opacity:.55;text-align:center;'>لا توجد تذاكر</p>"
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">الدعم الفني</b><a href="/" style="color:white;font-size:24px;"><i class="fas fa-home"></i></a></div>
    <div class="card"><h3 style="color:var(--accent);">فتح تذكرة جديدة</h3>{f'<p style="color:#2ecc71;">{h(message)}</p>' if message else ''}
    <form action="/ticket_action" method="GET"><input type="hidden" name="type" value="new"><input name="subject" placeholder="عنوان المشكلة" required><textarea name="message" placeholder="اشرح مشكلتك بالتفصيل" required style="width:100%;min-height:120px;margin-top:15px;padding:15px;border-radius:18px;background:rgba(255,255,255,.05);color:white;border:1px solid var(--border);"></textarea><button class="btn-send">إرسال التذكرة</button></form></div>
    <div class="card"><h3 style="color:var(--accent);">تذاكري</h3>{rows}</div><div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/settings" class="nav-item"><i class="fas fa-cog"></i>الإعدادات</a></div></body></html>"""

def get_terms_page():
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">{get_master_style()}</head><body>
    <div class="header"><b style="color:var(--accent);font-size:22px;">شروط الاستخدام</b><a href="/" style="color:white;font-size:24px;"><i class="fas fa-home"></i></a></div>
    <div class="card" style="line-height:2;"><h3 style="color:var(--accent);">استخدام مسؤول</h3><p>يجب استخدام الخدمات لأغراض تسويقية قانونية وملتزمة بسياسات المنصات. يمنع استخدام الموقع للانتحال أو الاحتيال أو نشر المحتوى المخالف.</p><h3 style="color:var(--accent);">الطلبات</h3><p>تأكد من صحة الرابط والكمية قبل تنفيذ الطلب. بعض الخدمات لا يمكن إلغاؤها بعد إرسالها للمزود.</p><h3 style="color:var(--accent);">الخصوصية</h3><p>نحفظ فقط البيانات اللازمة لتقديم الخدمة، ولا نطلب كلمات مرور حسابات التواصل الاجتماعي.</p></div>
    </body></html>"""

def admin_layout(title, content):
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{get_master_style()}
    <style>.admin-wrap{{max-width:900px;margin:0 auto}}.admin-table{{width:100%;border-collapse:collapse}}.admin-table th,.admin-table td{{padding:12px;border-bottom:1px solid var(--border);text-align:right}}.admin-table th{{color:var(--accent)}}.pill{{display:inline-block;padding:4px 10px;border-radius:12px;background:rgba(243,156,18,.18);color:var(--accent);font-size:12px}}</style></head><body>
    <div class="admin-wrap"><div class="header"><b style="color:var(--accent);font-size:22px;">{h(title)}</b><a href="/admin_panel" style="color:white;font-size:24px;"><i class="fas fa-arrow-right"></i></a></div>{content}</div></body></html>"""

def get_admin_reports_page(db):
    orders = db.get("orders", [])
    users = db.get("users", {})
    by_status = {}
    by_service = {}
    for order in orders:
        status = order.get("status", "غير معروف")
        service = order.get("svc", "غير معروف")
        by_status[status] = by_status.get(status, 0) + 1
        by_service[service] = by_service.get(service, 0) + float(order.get("cost", 0))
    status_rows = "".join(f"<tr><td>{h(k)}</td><td>{v}</td></tr>" for k, v in by_status.items()) or "<tr><td colspan='2'>لا توجد بيانات</td></tr>"
    service_rows = "".join(f"<tr><td>{h(k)}</td><td>{money(v)}</td></tr>" for k, v in sorted(by_service.items(), key=lambda x: x[1], reverse=True)) or "<tr><td colspan='2'>لا توجد بيانات</td></tr>"
    content = f"""<div class="card"><div class="stats-grid"><div class="stat-item"><i class="fas fa-users"></i><div class="stat-label">الأعضاء</div><div class="stat-value">{len(users)}</div></div><div class="stat-item"><i class="fas fa-shopping-bag"></i><div class="stat-label">الطلبات</div><div class="stat-value">{len(orders)}</div></div><div class="stat-item"><i class="fas fa-chart-line"></i><div class="stat-label">المبيعات</div><div class="stat-value">{money(sum(float(o.get('cost', 0)) for o in orders))}</div></div></div></div>
    <div class="card"><h3 style="color:var(--accent);">الطلبات حسب الحالة</h3><table class="admin-table"><tr><th>الحالة</th><th>العدد</th></tr>{status_rows}</table></div>
    <div class="card"><h3 style="color:var(--accent);">المبيعات حسب الخدمة</h3><table class="admin-table"><tr><th>الخدمة</th><th>القيمة</th></tr>{service_rows}</table></div>"""
    return admin_layout("التقارير والإحصائيات", content)

def get_admin_topups_page(db):
    rows = ""
    for topup in reversed(db.get("topups", [])):
        actions = ""
        if topup.get("status") == "قيد المراجعة":
            actions = f"""<a class="pill" href="/admin_action?type=approve_topup&id={h(topup.get('id'))}">قبول</a> <a class="pill" style="color:#ff4757;" href="/admin_action?type=reject_topup&id={h(topup.get('id'))}">رفض</a>"""
        rows += f"<tr><td>{h(topup.get('user'))}</td><td>{money(topup.get('amount'))}</td><td>{h(topup.get('method'))}</td><td>{h(topup.get('reference'))}</td><td>{h(topup.get('status'))}</td><td>{actions}</td></tr>"
    content = f"""<div class="card"><table class="admin-table"><tr><th>المستخدم</th><th>المبلغ</th><th>الطريقة</th><th>المرجع</th><th>الحالة</th><th>إجراء</th></tr>{rows or '<tr><td colspan="6">لا توجد طلبات شحن</td></tr>'}</table></div>"""
    return admin_layout("طلبات شحن الرصيد", content)

def get_admin_coupons_page(db):
    rows = "".join(f"<tr><td>{h(c.get('code'))}</td><td>{h(c.get('percent'))}%</td><td>{h(c.get('uses', 0))}/{h(c.get('max_uses', 0) or '∞')}</td><td>{'فعال' if c.get('active', True) else 'متوقف'}</td><td><a class='pill' href='/admin_action?type=del_coupon&code={h(c.get('code'))}'>حذف</a></td></tr>" for c in db.get("coupons", []))
    content = f"""<div class="card"><h3 style="color:var(--accent);">إضافة كوبون</h3><form action="/admin_action" method="GET"><input type="hidden" name="type" value="create_coupon"><input name="code" placeholder="الكود" required><input type="number" name="percent" min="1" max="100" placeholder="نسبة الخصم" required><input type="number" name="max_uses" min="0" placeholder="أقصى عدد استخدامات (0 بلا حد)"><button class="btn-send">حفظ الكوبون</button></form></div><div class="card"><table class="admin-table"><tr><th>الكود</th><th>الخصم</th><th>الاستخدام</th><th>الحالة</th><th>إجراء</th></tr>{rows or '<tr><td colspan="5">لا توجد كوبونات</td></tr>'}</table></div>"""
    return admin_layout("الكوبونات والعروض", content)

def get_admin_tickets_page(db):
    rows = ""
    for ticket in reversed(db.get("tickets", [])):
        replies = "<br>".join(f"{h(r.get('from'))}: {h(r.get('message'))}" for r in ticket.get("replies", []))
        rows += f"""<div class="card"><b>#{h(ticket.get('id'))} · {h(ticket.get('subject'))}</b><p style="opacity:.75;">المستخدم: {h(ticket.get('user'))}</p><p>{h(ticket.get('message'))}</p><p style="color:var(--accent);">{replies}</p><span class="pill">{h(ticket.get('status'))}</span><form action="/admin_action" method="GET"><input type="hidden" name="type" value="reply_ticket"><input type="hidden" name="id" value="{h(ticket.get('id'))}"><input name="message" placeholder="اكتب الرد" required><button class="btn-send">إرسال الرد</button></form><a class="pill" href="/admin_action?type=close_ticket&id={h(ticket.get('id'))}">إغلاق التذكرة</a></div>"""
    return admin_layout("تذاكر الدعم", rows or "<div class='card'>لا توجد تذاكر.</div>")

def get_admin_backup_page():
    content = """<div class="card" style="text-align:center;"><i class="fas fa-database" style="font-size:54px;color:var(--accent);"></i><h3>نسخة احتياطية للبيانات</h3><p style="opacity:.7;">ينشئ نسخة مؤرخة من بيانات المستخدمين والطلبات والإعدادات.</p><a class="btn-send" style="display:block;text-decoration:none;" href="/admin_action?type=backup">إنشاء نسخة احتياطية الآن</a></div>"""
    return admin_layout("النسخ الاحتياطي", content)

def get_admin_page(db):
    users, orders, services = db.get("users", {}), db.get("orders", []), db.get("services", [])
    total_profit = sum(float(o.get('cost', 0)) for o in orders)
    total_balances = sum(float(u.get('balance', 0)) for u in users.values())
    is_active = db.get("is_active", True)
    status_text = "✅ الموقع متصل" if is_active else "❌ وضع الصيانة"
    btn_color = "#2ecc71" if not is_active else "#e74c3c"
    pending_topups = len([t for t in db.get("topups", []) if t.get("status") == "قيد المراجعة"])
    open_tickets = len([t for t in db.get("tickets", []) if t.get("status") != "مغلقة"])

    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        :root {{ --accent: #f39c12; --glass: rgba(255, 255, 255, 0.08); --border: rgba(255, 255, 255, 0.1); }}
        * {{ box-sizing: border-box; font-family: 'Cairo', sans-serif; }}
        body {{ margin: 0; background: #0f172a; color: #fff; padding: 20px; }}
        .card {{ background: var(--glass); border: 1px solid var(--border); border-radius: 20px; padding: 20px; margin-bottom: 20px; backdrop-filter: blur(10px); }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .stat {{ background: rgba(0,0,0,0.2); padding: 15px; border-radius: 15px; text-align: center; border-bottom: 3px solid var(--accent); }}
        input, select, button {{ width: 100%; padding: 12px; margin: 8px 0; border-radius: 10px; border: 1px solid var(--border); background: rgba(255,255,255,0.05); color: #fff; }}
        .btn-action {{ background: var(--accent); color: #000; font-weight: bold; border: none; cursor: pointer; }}
        .user-row {{ display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid var(--border); }}
        .search-box {{ background: #fff !important; color: #000 !important; font-weight: bold; }}
    </style></head>
    <body>
        <h2 style="text-align:center;"><i class="fas fa-user-shield"></i> لوحة الإدارة</h2>
        <div class="grid">
            <div class="stat"><i class="fas fa-wallet"></i><br>الأرباح<br><b>${total_profit:.2f}</b></div>
            <div class="stat"><i class="fas fa-users"></i><br>الأعضاء<br><b>{len(users)}</b></div>
            <div class="stat"><i class="fas fa-coins"></i><br>إجمالي الأرصدة<br><b>${total_balances:.2f}</b></div>
            <div class="stat"><i class="fas fa-shopping-bag"></i><br>الطلبات<br><b>{len(orders)}</b></div>
        </div>
        <div class="card" style="text-align:center; margin-top:20px;">
            <h4>حالة الموقع حالياً: <span style="color:var(--accent)">{status_text}</span></h4>
            <a href="/admin_action?type=toggle_site"><button style="background:{btn_color}; color:white;">تبديل حالة الموقع</button></a>
        </div>
        <div class="card">
            <h4><i class="fas fa-magic"></i> إضافة خدمة تلقائية (API)</h4>
            <form action="/admin_action" method="GET">
                <input type="hidden" name="type" value="add_full_svc">
                <input name="n" placeholder="اسم الخدمة" required>
                <input name="c" placeholder="الفئة / القسم" required>
                <input type="number" step="0.01" name="p" placeholder="السعر لكل 1000" required>
                <input name="sid" placeholder="ID الخدمة عند المزود" required>
                <input name="url" placeholder="رابط API المزود" required>
                <input name="key" placeholder="API KEY المزود" required>
                <button class="btn-action">حفظ وإضافة الخدمة</button>
            </form>
        </div>
        <div class="card">
            <h4><i class="fas fa-users-cog"></i> إدارة أرصدة الأعضاء</h4>
            <input type="text" id="userInput" class="search-box" onkeyup="searchUsers()" placeholder="🔍 ابحث عن اسم المستخدم...">
            <div id="userList" style="max-height: 250px; overflow-y: auto;">
                {"".join([f'<div class="user-row" data-name="{n}"><span>{n}<br><small>${u["balance"]:.2f}</small></span><form action="/admin_action" style="display:flex; gap:5px;"><input type="hidden" name="type" value="adj_bal"><input type="hidden" name="u" value="{n}"><input type="number" name="a" placeholder="المبلغ" style="width:70px; margin:0; padding:5px;"><button name="mode" value="plus" style="width:35px; background:#2ecc71; margin:0;">+</button><button name="mode" value="minus" style="width:35px; background:#e74c3c; margin:0;">-</button></form></div>' for n, u in users.items()])}
            </div>
        </div>
        <div class="card">
        <div class="card" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 20px; padding: 20px; margin-top: 15px;">
            <h4 style="color: #f39c12; margin-bottom: 15px;"><i class="fas fa-trash-alt"></i> حذف الخدمات</h4>
            <div style="max-height: 250px; overflow-y: auto;">
                {"".join([f'''
                <div class="user-row" style="display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.03); background: rgba(0,0,0,0.2); margin-bottom: 8px; border-radius: 12px;">
                    <span style="color: #fff; font-size: 14px;">{s['name']}</span>
                    <a href="/admin_action?type=del_svc&id={s['id']}" 
                       onclick="return confirm('هل أنت متأكد من الحذف؟')" 
                       style="color: #ff4757; text-decoration: none; font-weight: bold; font-size: 12px; border: 1px solid #ff4757; padding: 5px 10px; border-radius: 8px;">
                       حذف <i class="fas fa-times-circle"></i>
                    </a>
                </div>
                ''' for s in db.get("services", [])])}
            </div>
        </div>

         <div class="card">
           <h4><i class="fas fa-toolbox"></i> مركز الإدارة</h4>
           <div class="grid">
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/admin_reports">التقارير</a>
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/admin_topups">الشحن ({pending_topups})</a>
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/admin_coupons">الكوبونات</a>
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/admin_tickets">التذاكر ({open_tickets})</a>
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/admin_action?type=sync_orders">تحديث الطلبات</a>
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/admin_backup">نسخ احتياطي</a>
             <a class="btn-action" style="text-decoration:none;text-align:center;" href="/settings">العودة للموقع</a>
           </div>
         </div>

        <script>
        // لاحظ الأقواس المزدوجة هنا لإصلاح خطأ Railway
        function searchUsers() {{ 
            let input = document.getElementById('userInput').value.toLowerCase();
            let rows = document.querySelectorAll('.user-row');
            rows.forEach(row => {{
                row.style.display = row.innerText.toLowerCase().includes(input) ? '' : 'none';
            }});
        }}
        </script>
    </body>
    </html>
    """


def get_user_page(db, user):
    u = db["users"][user]
    svcs = db.get("services", [])
    user_orders = [o for o in db.get("orders", []) if o.get('user') == user]
    cats = sorted(list(set([s['cat'] for s in svcs])))
    level, discount = tier_for_user(db, user)
    unread = len([n for n in db.get("notifications", []) if n.get("user") == user and not n.get("read")])

    return f"""<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {get_master_style()}
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        /* تحسين شكل القوائم المنسدلة المجمّلة */
        .custom-dropdown {{
            position: relative;
            width: 100%;
            margin-bottom: 20px;
            text-align: right;
        }}

        .dropdown-selected {{
            width: 100%;
            padding: 16px 20px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            color: #fff;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: 0.3s;
        }}

        .dropdown-selected:hover {{ border-color: var(--accent); }}

        .dropdown-options {{
            position: absolute;
            top: 110%;
            left: 0;
            width: 100%;
            background: #1a2a33;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            max-height: 250px;
            overflow-y: auto;
            display: none;
            z-index: 1000;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}

        .option-item {{
            padding: 12px 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 14px;
        }}

        .option-item:hover {{ background: rgba(243, 156, 18, 0.1); color: var(--accent); }}
        .option-item img {{ width: 22px; height: 22px; border-radius: 5px; }}
        
        .show {{ display: block !important; }}

        /* انيميشن النافذة الزجاجية */
        @keyframes slideUp {{ from {{ transform: translateY(50px); opacity:0; }} to {{ transform: translateY(0); opacity:1; }} }}
        .modal-detail-row {{ display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid rgba(255,255,255,0.05); }}
    </style>
</head>
<body>
    <div class="header">
        <div style="font-weight:900; color:var(--accent); font-size:22px;">{SITE_NAME}</div>
        <div style="display:flex;gap:18px;align-items:center;"><a href="/notifications" style="color:white;font-size:20px;"><i class="fas fa-bell"></i><sup style="color:var(--accent);">{unread}</sup></a><a href="/settings" style="color:white; font-size:24px;"><i class="fas fa-cog"></i></a></div>
    </div>

    <div class="card" style="border-color:rgba(243,156,18,.35);"><div style="font-size:13px;opacity:.75;">{h(db.get('announcement', ''))}</div></div>
    <div class="stats-grid" style="margin-top:20px;">
        <div class="stat-item"><i class="fas fa-wallet"></i><div class="stat-label">رصيدك</div><div class="stat-value">{money(u.get('balance'))}</div></div>
        <div class="stat-item"><i class="fas fa-shopping-bag"></i><div class="stat-label">الطلبات</div><div class="stat-value">{len(user_orders)}</div></div>
        <div class="stat-item"><i class="fas fa-star"></i><div class="stat-label">الفئة</div><div class="stat-value">{level}</div></div>
    </div>

    <div class="card">
        <h4 style="margin-top:0; color:var(--accent);"><i class="fas fa-shopping-cart"></i> إنشاء طلب جديد</h4>
        
        <form id="orderForm">
            <!-- قائمة الأقسام المجمّلة -->
            <span class="input-label">اختر القسم:</span>
            <div class="custom-dropdown">
                <div class="dropdown-selected" onclick="toggleDrop('cat-drop')">
                    <span id="cat-text">-- اضغط للاختيار --</span>
                    <i class="fas fa-chevron-down"></i>
                </div>
                <div class="dropdown-options" id="cat-drop">
                    {" ".join([f'<div class="option-item" onclick="selectCat(\'{c}\')"><span>{c}</span></div>' for c in cats])}
                </div>
            </div>

            <!-- قائمة الخدمات المجمّلة -->
            <span class="input-label">اختر الخدمة:</span>
            <div class="custom-dropdown">
                <div class="dropdown-selected" onclick="toggleDrop('svc-drop')">
                    <span id="svc-text">-- اختر القسم أولاً --</span>
                    <i class="fas fa-chevron-down"></i>
                </div>
                <div class="dropdown-options" id="svc-drop">
                    <!-- يتم تعبئتها بواسطة JS -->
                </div>
            </div>

            <input type="hidden" id="s_sel" name="sid">

            <span class="input-label">رابط الحساب / المنشور:</span>
            <input type="text" id="link" placeholder="ضع الرابط هنا..." required class="input-field" style="width:100%; padding:16px; border-radius:20px; background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.08); color:#fff; margin-bottom:20px; outline:none;">

            <span class="input-label">الكمية المطلوبة:</span>
            <input type="number" id="qty" placeholder="أدخل الكمية..." required class="input-field" style="width:100%; padding:16px; border-radius:20px; background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.08); color:#fff; margin-bottom:20px; outline:none;">
            <input type="text" id="coupon" placeholder="كود الخصم (اختياري)" class="input-field" style="width:100%; padding:16px; border-radius:20px; background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.08); color:#fff; margin-bottom:20px; outline:none;">

            <button type="button" onclick="submitOrder()" class="btn-send" style="width:100%; padding:18px; border-radius:22px; background:var(--accent); color:#000; font-weight:900; border:none; cursor:pointer;">
                <i class="fas fa-bolt"></i> تنفيذ الطلب الآن
            </button>
        </form>
    </div>

    <div id="orderModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:10000; align-items:center; justify-content:center;">
        <div class="card" id="modalBody" style="width:88%; max-width:380px; text-align:center; animation:slideUp 0.4s ease;">
        </div>
    </div>

    <div class="bottom-nav">
        <a href="/" class="nav-item active"><i class="fas fa-home"></i>الرئيسية</a>
        <a href="/topup" class="nav-item"><i class="fas fa-wallet"></i>الرصيد</a>
        <a href="/order_history" class="nav-item"><i class="fas fa-history"></i>الطلبات</a>
        <a href="/support" class="nav-item"><i class="fas fa-headset"></i>الدعم</a>
    </div>

    <script>
        const data = {json.dumps(svcs)};

        function toggleDrop(id) {{
            document.getElementById(id).classList.toggle('show');
        }}

        function selectCat(val) {{
            document.getElementById('cat-text').innerText = val;
            toggleDrop('cat-drop');
            loadSvcs(val);
        }}

        function loadSvcs(c) {{
            const sList = document.getElementById('svc-drop');
            const sText = document.getElementById('svc-text');
            sList.innerHTML = '';
            sText.innerText = '-- اختر الخدمة --';
            
            data.filter(i => i.cat === c).forEach(i => {{
                let div = document.createElement('div');
                div.className = 'option-item';
                div.innerHTML = `<span>${{i.name}} (${{i.price}}$)</span>`;
                div.onclick = function() {{
                    document.getElementById('s_sel').value = i.id;
                    sText.innerText = i.name;
                    toggleDrop('svc-drop');
                }};
                sList.appendChild(div);
            }});
        }}

        async function submitOrder() {{
            const modal = document.getElementById('orderModal');
            const modalBody = document.getElementById('modalBody');
            const sid = document.getElementById('s_sel').value;
            const qty = document.getElementById('qty').value;
            const link = document.getElementById('link').value;
            const coupon = document.getElementById('coupon').value;

            if(!sid || !qty || !link) {{ alert('أكمل البيانات أولاً صديقي!'); return; }}

            modal.style.display = 'flex';
            modalBody.innerHTML = '<i class="fas fa-spinner fa-spin" style="font-size:45px; color:var(--accent);"></i>';

            try {{
                const response = await fetch(`/place_order_api?sid=${{encodeURIComponent(sid)}}&qty=${{encodeURIComponent(qty)}}&link=${{encodeURIComponent(link)}}&coupon=${{encodeURIComponent(coupon)}}`);
                const res = await response.json();

                if(res.status === 'success') {{
                    modalBody.innerHTML = `
                        <i class="fas fa-check-circle" style="font-size:60px; color:#2ecc71"></i>
                        <h2 style="margin:10px 0;">تم الطلب!</h2>
                        <div style="margin:20px 0; background:rgba(255,255,255,0.05); padding:15px; border-radius:15px;">
                            <div class="modal-detail-row"><span>الخدمة:</span> <span>${{res.service}}</span></div>
                            <div class="modal-detail-row"><span>الكمية:</span> <span>${{qty}}</span></div>
                            <div class="modal-detail-row"><span>التكلفة:</span> <span>${{res.cost}}$</span></div>
                        </div>
                        <button onclick="location.reload()" class="btn-send" style="width:100%; padding:12px; border-radius:15px; background:var(--accent); color:#000; font-weight:bold; border:none;">موافق</button>
                    `;
                }} else {{
                    modalBody.innerHTML = `
                        <i class="fas fa-exclamation-circle" style="font-size:60px; color:#e74c3c"></i>
                        <h3 style="margin:10px 0;">فشل الطلب</h3>
                        <p style="color:rgba(255,255,255,0.7); margin-bottom:20px;">${{res.message}}</p>
                        <button onclick="document.getElementById('orderModal').style.display='none'" class="btn-send" style="width:100%; padding:12px; border-radius:15px; background:#e74c3c; color:#fff; border:none;">حاول مجدداً</button>
                    `;
                }}
            }} catch (e) {{
                modalBody.innerHTML = '<p>تم الطلب قيد التنفيذ♻️</p><button onclick="location.reload()">موافق</button>';
            }}
        }}

        // إغلاق القوائم عند الضغط خارجها
        window.onclick = function(event) {{
            if (!event.target.closest('.custom-dropdown')) {{
                document.querySelectorAll('.dropdown-options').forEach(d => d.classList.remove('show'));
            }}
        }}
    </script>
</body>
</html>"""




# --- [ 5. محرك السيرفر ] ---
class SpiderServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        db = load_db()
        ck = cookies.SimpleCookie(self.headers.get('Cookie'))
        user = ck['session_user'].value if 'session_user' in ck else None
        p, q = urlparse(self.path).path, parse_qs(urlparse(self.path).query)
        
        def res(h): 
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(h.encode('utf-8'))

        def json_res(payload, status=200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            
        def go(l): 
            self.send_response(302)
            self.send_header("Location", l)
            self.end_headers()

        # 1. الصفحات العامة (بدون تسجيل دخول)
        if p == "/auth":
            u_in, p_in = q.get('user',[''])[0], q.get('pass',[''])[0]
            if u_in in db['users'] and db['users'][u_in]['pass'] == hash_pass(p_in):
                self.send_response(302)
                self.send_header("Set-Cookie", f"session_user={urllib.parse.quote(u_in)}; Path=/; HttpOnly; SameSite=Lax")
                self.send_header("Location", "/")
                self.end_headers()
            else: res(get_welcome_page("اسم المستخدم أو كلمة المرور غير صحيحة"))
            return

        if p == "/register":
            nu, np = q.get('nu',[''])[0].strip(), q.get('np',[''])[0]
            phone = q.get('ph', [''])[0].strip()
            referral = q.get('ref', [''])[0].strip()
            if nu and len(np) >= 6 and nu not in db['users'] and all(c.isalnum() or c in "_-" for c in nu):
                db['users'][nu] = {
                    "pass": hash_pass(np), "balance": 0.0, "is_admin": False,
                    "phone": phone, "email": "", "lang": "ar",
                    "referral_code": make_referral_code(nu), "referred_by": "",
                    "referrals_earnings": 0.0, "created_at": now()
                }
                if referral:
                    owner = next((name for name, account in db["users"].items() if account.get("referral_code") == referral and name != nu), None)
                    if owner:
                        db["users"][nu]["referred_by"] = owner
                        notify(db, owner, "إحالة جديدة", f"سجّل مستخدم جديد عن طريقك: {nu}")
                audit(db, nu, "register", "تم إنشاء حساب جديد")
                save_db(db)
                go("/")
            else: res(get_welcome_page("تعذر إنشاء الحساب: تحقق من الاسم وكلمة المرور والبيانات المطلوبة"))
            return

        if p == "/forgot_password":
            res(get_forgot_password_page())
            return

        if p == "/forgot_action":
            username = q.get("user", [""])[0].strip()
            phone = q.get("phone", [""])[0].strip()
            new_password = q.get("new", [""])[0]
            account = db.get("users", {}).get(username)
            if not account or account.get("phone", "") != phone:
                res(get_forgot_password_page("بيانات التحقق غير صحيحة"))
            elif len(new_password) < 6:
                res(get_forgot_password_page("كلمة المرور يجب أن تكون 6 أحرف على الأقل"))
            else:
                account["pass"] = hash_pass(new_password)
                audit(db, username, "reset_password", "تم استرجاع كلمة المرور")
                save_db(db)
                res(get_forgot_password_page("تم تحديث كلمة المرور، يمكنك تسجيل الدخول الآن"))
            return

        if p == "/healthz":
            json_res({"status": "ok", "site": SITE_NAME, "active": db.get("is_active", True)})
            return

        if not user:
            res(get_welcome_page())
            return

        # 2. معالجة طلبات الـ API (هنا كان الخطأ)
        if p == "/place_order_api":
            try:
                if not db.get("is_active", True):
                    json_res({"status": "error", "message": "الموقع في وضع الصيانة حالياً"})
                    return
                sid = q.get('sid', [''])[0]
                link = q.get('link', [''])[0]
                qty = int(q.get('qty', ['0'])[0])
                coupon_code = q.get('coupon', [''])[0].strip().upper()
                svc = next((s for s in db.get('services', []) if s['id'] == sid), None)
                if not svc or qty <= 0 or not link.startswith(("http://", "https://")):
                    json_res({"status": "error", "message": "بيانات الطلب أو الرابط غير صحيح"})
                    return
                base_cost = (float(svc.get('price', 0)) / 1000) * qty
                level, tier_discount = tier_for_user(db, user)
                discount = tier_discount
                coupon = next((c for c in db.get("coupons", []) if str(c.get("code", "")).upper() == coupon_code and c.get("active", True)), None)
                if coupon and (not coupon.get("max_uses") or int(coupon.get("uses", 0)) < int(coupon.get("max_uses", 0))):
                    discount = min(100, discount + float(coupon.get("percent", 0)))
                cost = round(base_cost * (1 - discount / 100), 4)
                if db['users'][user]['balance'] < cost:
                    json_res({"status": "error", "message": "رصيدك غير كافٍ لشحن هذا الطلب"})
                    return
                if svc.get("api_url") and svc.get("api_key"):
                    success, result = send_api_order(svc['api_url'], svc['api_key'], svc.get('remote_id', ''), link, qty)
                    if not success:
                        json_res({"status": "error", "message": f"تعذر الاتصال بالمزود: {result}"})
                        return
                    remote_id, order_status = result, "قيد التنفيذ"
                else:
                    remote_id, order_status = f"LOCAL-{secrets.token_hex(4).upper()}", "قيد التنفيذ"
                db['users'][user]['balance'] -= cost
                order = {
                    "id": secrets.token_hex(6), "user": user, "svc": svc['name'],
                    "qty": qty, "link": link, "cost": cost, "status": order_status,
                    "remote_id": remote_id, "created_at": now(), "discount": discount
                }
                db['orders'].append(order)
                if coupon:
                    coupon["uses"] = int(coupon.get("uses", 0)) + 1
                notify(db, user, "تم استلام طلبك", f"طلب {svc['name']} قيد التنفيذ الآن")
                audit(db, user, "create_order", f"تم إنشاء طلب للخدمة {svc['name']}")
                save_db(db)
                json_res({"status": "success", "service": svc['name'], "cost": f"{cost:.2f}", "discount": discount, "order_id": order["id"]})
            except Exception as e:
                json_res({"status": "error", "message": "حدث خطأ أثناء معالجة الطلب"})
            return

        # أدوات الحساب والصفحات الجديدة
        if p == "/topup":
            res(get_topup_page(db, user))
            return

        if p == "/topup_action":
            if q.get("type", [""])[0] == "request":
                try:
                    amount = float(q.get("amount", ["0"])[0])
                except ValueError:
                    amount = 0
                if amount <= 0:
                    res(get_topup_page(db, user, "أدخل مبلغاً صحيحاً"))
                    return
                topup = {
                    "id": secrets.token_hex(6), "user": user, "amount": amount,
                    "method": q.get("method", [""])[0], "reference": q.get("reference", [""])[0],
                    "status": "قيد المراجعة", "created_at": now()
                }
                db.setdefault("topups", []).append(topup)
                for admin_name, account in db["users"].items():
                    if account.get("is_admin"):
                        notify(db, admin_name, "طلب شحن جديد", f"طلب {user} شحن رصيد بقيمة {money(amount)}")
                audit(db, user, "topup_request", f"طلب شحن بقيمة {amount}")
                save_db(db)
                res(get_topup_page(db, user, "تم إرسال طلب الشحن للمراجعة"))
            return

        if p == "/notifications":
            res(get_notifications_page(db, user))
            return

        if p == "/referrals":
            res(get_referrals_page(db, user))
            return

        if p == "/change_password":
            res(get_change_password_page())
            return

        if p == "/change_password_action":
            old, new, confirm = q.get("old", [""])[0], q.get("new", [""])[0], q.get("confirm", [""])[0]
            if db["users"][user].get("pass") != hash_pass(old):
                res(get_change_password_page("كلمة المرور الحالية غير صحيحة"))
            elif len(new) < 6 or new != confirm:
                res(get_change_password_page("تأكد من تطابق كلمة المرور الجديدة وأن تكون 6 أحرف على الأقل"))
            else:
                db["users"][user]["pass"] = hash_pass(new)
                audit(db, user, "change_password", "تم تغيير كلمة المرور")
                save_db(db)
                res(get_change_password_page("تم تغيير كلمة المرور بنجاح"))
            return

        if p == "/support":
            res(get_support_page(db, user))
            return

        if p == "/ticket_action":
            ticket_type = q.get("type", [""])[0]
            if ticket_type == "new":
                ticket = {
                    "id": secrets.token_hex(4).upper(), "user": user,
                    "subject": q.get("subject", [""])[0], "message": q.get("message", [""])[0],
                    "status": "مفتوحة", "created_at": now(), "replies": []
                }
                db.setdefault("tickets", []).append(ticket)
                audit(db, user, "open_ticket", f"فتح تذكرة {ticket['id']}")
                save_db(db)
                res(get_support_page(db, user, "تم إرسال التذكرة، سيتواصل معك فريق الدعم"))
            return

        if p == "/terms":
            res(get_terms_page())
            return

        # توجيه الصفحات
        if p == "/logout":
            self.send_response(302)
            self.send_header("Set-Cookie", "session_user=; Max-Age=0; Path=/")
            self.send_header("Location", "/")
            self.end_headers()
            
        elif p == "/admin_panel":
            if db['users'].get(user, {}).get('is_admin'): 
                res(get_admin_page(db))
            else: 
                go("/")
                
        elif p == "/settings":
            res(get_settings_page(db, user))
            
        elif p == "/order_history":
            res(get_orders_page(db, user))
            
        elif p == "/admin_reports":
            if db['users'].get(user, {}).get('is_admin'):
                res(get_admin_reports_page(db))
            else:
                go("/")

        elif p == "/admin_topups":
            if db['users'].get(user, {}).get('is_admin'):
                res(get_admin_topups_page(db))
            else:
                go("/")

        elif p == "/admin_coupons":
            if db['users'].get(user, {}).get('is_admin'):
                res(get_admin_coupons_page(db))
            else:
                go("/")

        elif p == "/admin_tickets":
            if db['users'].get(user, {}).get('is_admin'):
                res(get_admin_tickets_page(db))
            else:
                go("/")

        elif p == "/admin_backup":
            if db['users'].get(user, {}).get('is_admin'):
                res(get_admin_backup_page())
            else:
                go("/")

        elif p == "/admin_action":
            if not db['users'].get(user, {}).get('is_admin'):
                go("/")
                return
            t = q.get('type', [''])[0]
            
            # 1. تعديل الرصيد
            if t == "adj_bal":
                target, amt, mode = q.get('u',[''])[0], float(q.get('a',['0'])[0]), q.get('mode',[''])[0]
                db['users'][target]['balance'] += amt if mode == "plus" else -amt
                notify(db, target, "تحديث الرصيد", f"تم تعديل رصيدك بمبلغ {money(amt)}")
                audit(db, user, "adjust_balance", f"تم تعديل رصيد {target}")
                save_db(db)
                go("/admin_panel")
            
            # 2. إضافة خدمة تلقائية
            elif t == "add_full_svc":
                new_id = str(len(db.get('services', [])) + 1)
                db.setdefault('services', []).append({
                    "id": new_id, 
                    "name": q.get('n', [''])[0], 
                    "cat": q.get('c', [''])[0], 
                    "price": float(q.get('p', ['0'])[0]), 
                    "remote_id": q.get('sid', [''])[0],
                    "api_url": q.get('url', [''])[0], 
                    "api_key": q.get('key', [''])[0]
                })
                audit(db, user, "add_service", q.get('n', [''])[0])
                save_db(db)
                go("/admin_panel")

            # 3. حذف الخدمة (الإضافة الجديدة)
            elif t == "del_svc":
                svc_id = q.get('id', [''])[0]
                services = db.get('services', [])
                # تصفية القائمة وحذف الخدمة المطلوبة
                db['services'] = [s for s in services if str(s.get('id')) != str(svc_id)]
                audit(db, user, "delete_service", svc_id)
                save_db(db)
                go("/admin_panel")

            elif t == "toggle_site":
                db["is_active"] = not db.get("is_active", True)
                audit(db, user, "toggle_site", str(db["is_active"]))
                save_db(db)
                go("/admin_panel")

            elif t in ("approve_topup", "reject_topup"):
                topup_id = q.get("id", [""])[0]
                topup = next((item for item in db.get("topups", []) if item.get("id") == topup_id), None)
                if topup and topup.get("status") == "قيد المراجعة":
                    if t == "approve_topup":
                        amount = float(topup.get("amount", 0))
                        db["users"].setdefault(topup["user"], {}).setdefault("balance", 0)
                        db["users"][topup["user"]]["balance"] += amount
                        db["users"][topup["user"]]["referrals_earnings"] = db["users"][topup["user"]].get("referrals_earnings", 0)
                        referred_by = db["users"][topup["user"]].get("referred_by")
                        if referred_by and referred_by in db["users"]:
                            commission = amount * float(db.get("referral_percent", 5)) / 100
                            db["users"][referred_by]["balance"] += commission
                            db["users"][referred_by]["referrals_earnings"] = db["users"][referred_by].get("referrals_earnings", 0) + commission
                            notify(db, referred_by, "عمولة إحالة", f"أضيفت لك عمولة بقيمة {money(commission)}")
                        topup["status"] = "مقبول"
                        notify(db, topup["user"], "تم قبول الشحن", f"تمت إضافة {money(amount)} إلى رصيدك")
                    else:
                        topup["status"] = "مرفوض"
                        notify(db, topup["user"], "تم رفض طلب الشحن", "يمكنك فتح تذكرة للدعم إذا كان هناك خطأ")
                    audit(db, user, t, topup_id)
                    save_db(db)
                go("/admin_topups")

            elif t == "create_coupon":
                code = q.get("code", [""])[0].strip().upper()
                try:
                    percent = max(1, min(100, float(q.get("percent", ["0"])[0])))
                    max_uses = max(0, int(q.get("max_uses", ["0"])[0] or 0))
                except ValueError:
                    percent, max_uses = 0, 0
                if code and percent:
                    db.setdefault("coupons", []).append({"code": code, "percent": percent, "max_uses": max_uses, "uses": 0, "active": True, "created_at": now()})
                    audit(db, user, "create_coupon", code)
                    save_db(db)
                go("/admin_coupons")

            elif t == "del_coupon":
                code = q.get("code", [""])[0].strip().upper()
                db["coupons"] = [c for c in db.get("coupons", []) if str(c.get("code", "")).upper() != code]
                audit(db, user, "delete_coupon", code)
                save_db(db)
                go("/admin_coupons")

            elif t == "reply_ticket":
                ticket_id = q.get("id", [""])[0]
                ticket = next((item for item in db.get("tickets", []) if item.get("id") == ticket_id), None)
                if ticket:
                    message = q.get("message", [""])[0]
                    ticket.setdefault("replies", []).append({"from": user, "message": message, "created_at": now()})
                    ticket["status"] = "قيد المتابعة"
                    notify(db, ticket["user"], "رد جديد من الدعم", f"تم الرد على تذكرتك #{ticket_id}")
                    audit(db, user, "reply_ticket", ticket_id)
                    save_db(db)
                go("/admin_tickets")

            elif t == "close_ticket":
                ticket_id = q.get("id", [""])[0]
                ticket = next((item for item in db.get("tickets", []) if item.get("id") == ticket_id), None)
                if ticket:
                    ticket["status"] = "مغلقة"
                    audit(db, user, "close_ticket", ticket_id)
                    save_db(db)
                go("/admin_tickets")

            elif t == "sync_orders":
                changed_orders = 0
                for order in db.get("orders", []):
                    if order.get("status") not in ("قيد التنفيذ", "معلّق") or not order.get("remote_id"):
                        continue
                    service = next((item for item in db.get("services", []) if item.get("name") == order.get("svc")), None)
                    if not service or not service.get("api_url") or not service.get("api_key") or str(order.get("remote_id", "")).startswith("LOCAL-"):
                        continue
                    success, status = sync_api_order(service["api_url"], service["api_key"], order["remote_id"])
                    if success and status != order.get("status"):
                        order["status"] = status
                        changed_orders += 1
                        notify(db, order["user"], "تحديث حالة الطلب", f"طلبك {order.get('svc')} أصبح: {status}")
                audit(db, user, "sync_orders", f"تم تحديث {changed_orders} طلب")
                save_db(db)
                res(f"""<!doctype html><html lang="ar" dir="rtl"><body style="background:#0f172a;color:white;font-family:Arial;text-align:center;padding:80px;"><h2>تم تحديث الطلبات</h2><p>تم تعديل حالة {changed_orders} طلب.</p><a href="/admin_panel" style="color:#f39c12;">العودة للوحة الإدارة</a></body></html>""")
                return

            elif t == "backup":
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = DB_FILE + f".backup_{stamp}"
                save_db(db)
                shutil.copy2(DB_FILE, backup_file)
                audit(db, user, "backup", backup_file)
                save_db(db)
                res(f"""<!doctype html><html lang="ar" dir="rtl"><body style="background:#0f172a;color:white;font-family:Arial;text-align:center;padding:80px;"><h2>تم إنشاء النسخة الاحتياطية بنجاح</h2><p>{h(os.path.basename(backup_file))}</p><a href="/admin_panel" style="color:#f39c12;">العودة للوحة الإدارة</a></body></html>""")
                return

        else:
            res(get_user_page(db, user))
                


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SpiderServer) as httpd:
        print(f"🚀 السيرفر يعمل الآن: http://localhost:{PORT}")
        httpd.serve_forever()
