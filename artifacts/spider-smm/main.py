import http.server
import os
import socketserver
import json
import hashlib
import urllib.request
import urllib.parse
from urllib.parse import parse_qs, urlparse
from http import cookies

# --- [ 1. الإعدادات والبيانات الأساسية ] ---
PORT = int(os.environ.get("PORT", 8080))
DB_FILE = "spider_master_database.json"
SITE_NAME = "SpiderSmm"
TELEGRAM_USER = "SmmSpider" 

if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- [ 2. وظائف قاعدة البيانات ] ---
def load_db():
    if not os.path.exists(DB_FILE):
        data = {
            "users": {"admin": {"pass": hash_pass("nbel2712"), "balance": 0, "is_admin": True, "phone": "000"}},
            "services": [], 
            "orders": [], 
            "announcement": "مرحباً بك في عالم الفخامة الرقمية!",
            "is_active": True
        }
        save_db(data)
        return data
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return load_db()

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

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
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;900&display=swap');
            
            :root {{
                --gold: #f39c12;
                --dark-bg: #050a14;
                --glass-bg: rgba(255, 255, 255, 0.03);
                --border: rgba(255, 255, 255, 0.08);
            }}

            * {{
                box-sizing: border-box;
                font-family: 'Cairo', sans-serif;
                margin: 0;
                padding: 0;
                -webkit-tap-highlight-color: transparent;
            }}

            html, body {{
                width: 100%;
                overflow-x: hidden; /* يمنع الحركة الجانبية تماماً */
                background: var(--dark-bg);
                color: #fff;
                line-height: 1.6;
            }}

            /* خلفية أورورا ناعمة مريحة للعين */
            body::before {{
                content: "";
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: radial-gradient(circle at 10% 20%, rgba(243, 156, 18, 0.12) 0%, transparent 40%),
                            radial-gradient(circle at 90% 80%, rgba(44, 83, 100, 0.18) 0%, transparent 40%);
                z-index: -1;
            }}

            .main-wrapper {{
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 40px 15px;
                width: 100%;
            }}

            /* شعار السبايدر المتوهج والمتحرك */
            .logo-section {{
                margin-bottom: 30px;
                text-align: center;
            }}

            .logo-section i {{
                font-size: 85px;
                color: var(--gold);
                filter: drop-shadow(0 0 25px rgba(243, 156, 18, 0.6));
                animation: floatAnim 4s infinite ease-in-out;
            }}

            @keyframes floatAnim {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-15px); }}
            }}

            /* الكرت الزجاجي الاحترافي */
            .auth-card {{
                background: var(--glass-bg);
                backdrop-filter: blur(25px);
                -webkit-backdrop-filter: blur(25px);
                border: 1px solid var(--border);
                border-radius: 40px;
                padding: 40px 25px;
                width: 100%;
                max-width: 420px;
                box-shadow: 0 50px 100px rgba(0,0,0,0.8);
                z-index: 5;
            }}

            h1 {{ font-size: 26px; font-weight: 900; text-align: center; margin-bottom: 5px; }}
            .sub-title {{ color: rgba(255,255,255,0.4); text-align: center; margin-bottom: 35px; font-size: 13px; }}

            /* حقول الإدخال */
            .field-box {{ position: relative; margin-bottom: 18px; }}
            .field-box i {{ position: absolute; right: 20px; top: 50%; transform: translateY(-50%); color: var(--gold); font-size: 18px; }}
            
            input {{
                width: 100%;
                padding: 18px 55px 18px 20px;
                border-radius: 22px;
                border: 1px solid rgba(255,255,255,0.1);
                background: rgba(0,0,0,0.3);
                color: #fff;
                font-size: 16px;
                outline: none;
                transition: all 0.3s ease;
            }}

            input:focus {{ border-color: var(--gold); background: rgba(243, 156, 18, 0.05); }}

            .action-btn {{
                width: 100%;
                padding: 18px;
                border-radius: 22px;
                border: none;
                background: linear-gradient(135deg, #f39c12, #e67e22);
                color: #000;
                font-weight: 900;
                font-size: 18px;
                cursor: pointer;
                box-shadow: 0 15px 35px rgba(243, 156, 18, 0.4);
                margin-top: 10px;
                transition: 0.3s;
            }}

            .action-btn:active {{ transform: scale(0.98); }}

            .switch-btn {{
                text-align: center;
                margin-top: 25px;
                color: rgba(255,255,255,0.5);
                font-size: 14px;
                cursor: pointer;
            }}

            .switch-btn b {{ color: var(--gold); text-decoration: underline; padding-right: 5px; }}

            /* قسم مميزات المتجر */
            .why-us {{ width: 100%; max-width: 450px; margin-top: 50px; }}
            .why-title {{ text-align: center; font-weight: 900; color: var(--gold); margin-bottom: 25px; font-size: 20px; }}
            
            .info-card {{
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.05);
                padding: 22px;
                border-radius: 28px;
                display: flex;
                align-items: center;
                gap: 18px;
                margin-bottom: 15px;
            }}

            .info-card i {{
                font-size: 24px;
                color: #000;
                background: var(--gold);
                width: 55px;
                height: 55px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 18px;
                flex-shrink: 0;
            }}

            .info-text h4 {{ font-size: 16px; margin-bottom: 3px; }}
            .info-text p {{ font-size: 12px; color: rgba(255,255,255,0.5); line-height: 1.4; }}
        </style>
    </head>
    <body>
        <div class="main-wrapper">
            
            <div class="logo-section">
                <i class="fas fa-spider"></i>
            </div>

            <div class="auth-card">
                
                <div id="login-form">
                    <h1>تسجيل الدخول</h1>
                    <p class="sub-title">مرحباً بك في متجر {SITE_NAME}</p>
                    {f'<p style="color:#ff4757; text-align:center; font-size:14px; margin-bottom:15px; font-weight:bold;">{{error}}</p>' if error else ''}
                    <form action="/auth">
                        <div class="field-box">
                            <i class="fas fa-user"></i>
                            <input type="text" name="user" placeholder="اسم المستخدم" required>
                        </div>
                        <div class="field-box">
                            <i class="fas fa-lock"></i>
                            <input type="password" name="pass" placeholder="كلمة المرور" required>
                        </div>
                        <button type="submit" class="action-btn">دخول آمن</button>
                    </form>
                    <div class="switch-btn" onclick="toggleAuth()">ليس لديك حساب؟ <b>إنشاء عضوية</b></div>
                </div>

                <div id="reg-form" style="display:none;">
                    <h1>عضوية جديدة</h1>
                    <p class="sub-title">انضم إلينا الآن واستمتع بالخدمات</p>
                    <form action="/register">
                        <div class="field-box">
                            <i class="fas fa-user-plus"></i>
                            <input type="text" name="nu" placeholder="اختر اسم مستخدم" required>
                        </div>
                        <div class="field-box">
                            <i class="fas fa-key"></i>
                            <input type="password" name="np" placeholder="كلمة المرور" required>
                        </div>
                        <div class="field-box">
                            <i class="fas fa-phone"></i>
                            <input type="tel" name="ph" placeholder="رقم الهاتف" required>
                        </div>
                        <button type="submit" class="action-btn">تأكيد الحساب</button>
                    </form>
                    <div class="switch-btn" onclick="toggleAuth()">لديك حساب بالفعل؟ <b>سجل دخولك</b></div>
                </div>

            </div>

            <div class="why-us">
                <h3 class="why-title">لماذا تختار متجرنا؟</h3>
                
                <div class="info-card">
                    <i class="fas fa-bolt"></i>
                    <div class="info-text">
                        <h4>سرعة خرافية</h4>
                        <p>نظامنا عالمي يضمن تنفيذ طلبك خلال ثوانٍ من الدفع. .</p>
                    </div>
                </div>

                <div class="info-card">
                    <i class="fas fa-gem"></i>
                    <div class="info-text">
                        <h4>جودة VIP</h4>
                        <p>نوفر لك اشتراكات أصلية ومضمونة لجميع التطبيقات والبرامج بأسعار تنافسية.</p>
                    </div>
                </div>

                <div class="info-card">
                    <i class="fas fa-user-shield"></i>
                    <div class="info-text">
                        <h4>حماية خصوصيتك</h4>
                        <p>لا نحتاج لمعلومات سرية، فقط الرابط ونحن نتكفل بالباقي بأمان تام.</p>
                    </div>
                </div>
            </div>

            <p style="margin-top:40px; color:rgba(255,255,255,0.15); font-size:11px;">{SITE_NAME} © 2026</p>
        </div>

        <script>
            function toggleAuth() {{
                const l = document.getElementById('login-form'), r = document.getElementById('reg-form');
                if(l.style.display === 'none') {{
                    l.style.display = 'block';
                    r.style.display = 'none';
                }} else {{
                    l.style.display = 'none';
                    r.style.display = 'block';
                }}
            }}
        </script>
    </body>
    </html>
    """
    

def get_orders_page(db, user):
    orders = [o for o in db.get("orders", []) if o.get('user') == user]
    orders_html = ""
    for o in reversed(orders):
        status_color = "#2ecc71" if o['status'] == "مكتمل" else "#f39c12"
        orders_html += f"""
        <div class="order-row">
            <div>
                <div style="font-weight:bold;">{o['svc']}</div>
                <div style="font-size:12px; opacity:0.6;">الكمية: {o['qty']} | التكلفة: ${o['cost']:.2f}</div>
            </div>
            <div style="color:{status_color}; font-weight:bold; font-size:14px;">{o['status']}</div>
        </div>"""
    if not orders_html:
        orders_html = "<p style='text-align:center; opacity:0.5; margin-top:50px;'>ليس لديك طلبات سابقة</p>"
    return f"""<!DOCTYPE html><html lang="ar"><head><meta charset="UTF-8">{get_master_style()}</head><body>
        <div class="header"><div style="font-weight:900; color:var(--accent); font-size:22px;">سجل طلباتي</div><a href="/" style="color:white; font-size:24px;"><i class="fas fa-times"></i></a></div>
        <div class="card">{orders_html}</div>
        <div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="/settings" class="nav-item"><i class="fas fa-cog"></i>الإعدادات</a></div>
    </body></html>"""

def get_settings_page(db, user):
    u = db["users"][user]
    admin_item = f"""<a href="/admin_panel" class="settings-item"><i class="fas fa-user-shield"></i><span class="text">لوحة التحكم للإدارة</span><i class="fas fa-chevron-left chevron"></i></a>""" if u.get('is_admin') else ""
    return f"""<!DOCTYPE html><html lang="ar"><head><meta charset="UTF-8">{get_master_style()}</head><body>
        <div class="header"><div style="font-weight:900; color:var(--accent); font-size:22px;">{SITE_NAME}</div><a href="/" style="color:white; font-size:24px;"><i class="fas fa-times"></i></a></div>
        <div class="card" style="text-align:center;">
            <div style="width:80px; height:80px; background:rgba(243,156,18,0.1); border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 15px; border:1px solid var(--accent);"><i class="fas fa-user" style="font-size:35px; color:var(--accent);"></i></div>
            <h2 style="margin:0;">{user}</h2><div class="badge" style="margin-top:10px;">الرصيد: ${u['balance']:.2f}</div>
        </div>
        <div class="settings-group">
            <div class="settings-title">الحساب والمالية</div>
            <div class="settings-list">
                <a href="/order_history" class="settings-item"><i class="fas fa-history"></i><span class="text">سجل طلباتي</span><i class="fas fa-chevron-left chevron"></i></a>
                <a href="https://t.me/{TELEGRAM_USER}" class="settings-item"><i class="fas fa-wallet"></i><span class="text">شحن الرصيد</span><i class="fas fa-chevron-left chevron"></i></a>
                {admin_item}
            </div>
        </div>
        <div class="settings-group"><div class="settings-title">الدعم والمعلومات</div><div class="settings-list">
            <a href="https://t.me/{TELEGRAM_USER}" target="_blank" class="settings-item"><i class="fab fa-telegram-plane"></i><span class="text">قناتنا على التليجرام</span><i class="fas fa-chevron-left chevron"></i></a>
            <a href="/terms" class="settings-item"><i class="fas fa-info-circle"></i><span class="text">شروط الاستخدام</span><i class="fas fa-chevron-left chevron"></i></a>
        </div></div>
        <div class="settings-group" style="margin-bottom:120px;"><div class="settings-list"><a href="/logout" class="settings-item" style="color:#ff4757;"><i class="fas fa-sign-out-alt" style="color:#ff4757;"></i><span class="text">تسجيل الخروج</span></a></div></div>
        <div class="bottom-nav"><a href="/" class="nav-item"><i class="fas fa-home"></i>الرئيسية</a><a href="https://t.me/{TELEGRAM_USER}" class="nav-item"><i class="fab fa-telegram"></i>الدعم الفني</a></div>
    </body></html>"""

def get_admin_page(db):
    users, orders, services = db.get("users", {}), db.get("orders", []), db.get("services", [])
    total_profit = sum(float(o.get('cost', 0)) for o in orders)
    total_balances = sum(float(u.get('balance', 0)) for u in users.values())
    is_active = db.get("is_active", True)
    status_text = "✅ الموقع متصل" if is_active else "❌ وضع الصيانة"
    btn_color = "#2ecc71" if not is_active else "#e74c3c"

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
        <a href="/settings" style="color:white; font-size:24px;"><i class="fas fa-cog"></i></a>
    </div>

    <div class="stats-grid" style="margin-top:20px;">
        <div class="stat-item"><i class="fas fa-wallet"></i><div class="stat-label">رصيدك</div><div class="stat-value">${u.get('balance', 0)}</div></div>
        <div class="stat-item"><i class="fas fa-shopping-bag"></i><div class="stat-label">الطلبات</div><div class="stat-value">{len(user_orders)}</div></div>
        <div class="stat-item"><i class="fas fa-star"></i><div class="stat-label">الفئة</div><div class="stat-value">VIP</div></div>
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
        <a href="https://t.me/{TELEGRAM_USER}" class="nav-item"><i class="fab fa-telegram"></i>الدعم</a>
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

            if(!sid || !qty || !link) {{ alert('أكمل البيانات أولاً صديقي!'); return; }}

            modal.style.display = 'flex';
            modalBody.innerHTML = '<i class="fas fa-spinner fa-spin" style="font-size:45px; color:var(--accent);"></i>';

            try {{
                const response = await fetch(`/place_order_api?sid=${{sid}}&qty=${{qty}}&link=${{link}}`);
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
            self.end_headers()
            self.wfile.write(h.encode('utf-8'))
            
        def go(l): 
            self.send_response(302)
            self.send_header("Location", l)
            self.end_headers()

        # 1. الصفحات العامة (بدون تسجيل دخول)
        if p == "/auth":
            u_in, p_in = q.get('user',[''])[0], q.get('pass',[''])[0]
            if u_in in db['users'] and db['users'][u_in]['pass'] == hash_pass(p_in):
                self.send_response(302)
                self.send_header("Set-Cookie", f"session_user={u_in}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
            else: res("خطأ في بيانات الدخول!")
            return

        if p == "/register":
            nu, np = q.get('nu',[''])[0], q.get('np',[''])[0]
            if nu and np and nu not in db['users']:
                db['users'][nu] = {"pass": hash_pass(np), "balance": 0.0, "is_admin": False}
                save_db(db)
                go("/")
            else: res("خطأ: المستخدم موجود بالفعل")
            return

        if not user:
            res(get_welcome_page())
            return

        # 2. معالجة طلبات الـ API (هنا كان الخطأ)
        if p == "/place_order_api":
            try:
                sid = q.get('sid', [''])[0]
                link = q.get('link', [''])[0]
                qty = int(q.get('qty', ['0'])[0])
                
                svc = next((s for s in db.get('services', []) if s['id'] == sid), None)
                if svc and qty > 0:
                    cost = (float(svc['price']) / 1000) * qty
                    if db['users'][user]['balance'] >= cost:
                        success, result = send_api_order(svc['api_url'], svc['api_key'], svc['remote_id'], link, qty)
                        if success:
                            db['users'][user]['balance'] -= cost
                            db['orders'].append({"user": user, "svc": svc['name'], "qty": qty, "cost": cost, "status": "مكتمل", "remote_id": result})
                            save_db(db)
                            res("<html><script>alert('تم الطلب بنجاح!'); window.location='/';</script></html>")
                        else:
                            res(f"<html><script>alert('خطأ من المزود: {result}'); window.location='/';</script></html>")
                    else:
                        res("<html><script>alert('رصيدك غير كافٍ!'); window.location='/';</script></html>")
                else:
                    res("<html><script>alert('بيانات الطلب غير صحيحة'); window.location='/';</script></html>")
            except Exception as e:
                res(f"<html><script>alert('حدث خطأ: {str(e)}'); window.location='/';</script></html>")
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
            
        elif p == "/admin_action":
            t = q.get('type', [''])[0]
            
            # 1. تعديل الرصيد
            if t == "adj_bal":
                target, amt, mode = q.get('u',[''])[0], float(q.get('a',['0'])[0]), q.get('mode',[''])[0]
                db['users'][target]['balance'] += amt if mode == "plus" else -amt
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
                save_db(db)
                go("/admin_panel")

            # 3. حذف الخدمة (الإضافة الجديدة)
            elif t == "del_svc":
                svc_id = q.get('id', [''])[0]
                services = db.get('services', [])
                # تصفية القائمة وحذف الخدمة المطلوبة
                db['services'] = [s for s in services if str(s.get('id')) != str(svc_id)]
                save_db(db)
                go("/admin_panel")

        else:
            res(get_user_page(db, user))
                


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SpiderServer) as httpd:
        print(f"🚀 السيرفر يعمل الآن: http://localhost:{PORT}")
        httpd.serve_forever()
