from flask import Flask, request, render_template_string, jsonify, session
import smtplib
import dns.resolver
import socket
import concurrent.futures
import threading
import time
import re
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'gmail_verifier_secret_key_2024'

# ============================================
# الإعدادات
# ============================================
MAX_WORKERS = 100
SOCKET_TIMEOUT = 5
REQUEST_DELAY = 0.05

# خوادم MX لجيميل
MX_SERVERS = [
    'gmail-smtp-in.l.google.com',
    'alt1.gmail-smtp-in.l.google.com',
    'alt2.gmail-smtp-in.l.google.com',
    'alt3.gmail-smtp-in.l.google.com',
    'alt4.gmail-smtp-in.l.google.com'
]

# ============================================
# قالب HTML
# ============================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gmail Verifier - فحص حسابات جوجل</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            font-size: 14px;
        }
        .main-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .input-area {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: bold;
            color: #333;
        }
        textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-family: monospace;
            font-size: 14px;
            resize: vertical;
            direction: ltr;
            text-align: left;
        }
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .example {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 16px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
            margin-top: 10px;
        }
        button:hover { transform: scale(1.02); }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .results {
            margin-top: 30px;
        }
        .result-section {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .result-section h3 {
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid;
        }
        .live-section h3 { color: #28a745; border-bottom-color: #28a745; }
        .disabled-section h3 { color: #dc3545; border-bottom-color: #dc3545; }
        .error-section h3 { color: #ffc107; border-bottom-color: #ffc107; }
        .stats {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            flex: 1;
            min-width: 100px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .stat-number {
            font-size: 28px;
            font-weight: bold;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
        }
        .live-number { color: #28a745; }
        .disabled-number { color: #dc3545; }
        .error-number { color: #ffc107; }
        .email-list {
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            background: white;
            padding: 10px;
            border-radius: 8px;
        }
        .email-item {
            padding: 5px;
            border-bottom: 1px solid #eee;
        }
        .progress {
            display: none;
            margin-top: 20px;
        }
        .progress.show {
            display: block;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }
        .progress-text {
            text-align: center;
            margin-top: 10px;
            font-size: 12px;
            color: #666;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        footer {
            text-align: center;
            font-size: 12px;
            color: rgba(255,255,255,0.7);
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Gmail Verifier</h1>
            <div class="subtitle">فحص حسابات جوجل - تحديد النشطة والمعطلة</div>
        </div>

        <div class="main-card">
            <div class="input-area">
                <label>📧 أدخل حسابات Gmail (حساب واحد في كل سطر)</label>
                <textarea id="emailsInput" rows="10" placeholder="example1@gmail.com&#10;example2@gmail.com&#10;example3@gmail.com"></textarea>
                <div class="example">💡 مثال: username@gmail.com</div>
            </div>

            <button onclick="startVerification()" id="verifyBtn">🔎 بدء الفحص</button>

            <div class="progress" id="progress">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText">جاري الفحص...</div>
            </div>
        </div>

        <div class="results" id="results" style="display: none;">
            <div class="stats" id="stats"></div>
            
            <div class="result-section live-section" id="liveSection">
                <h3>✅ الحسابات النشطة (Live)</h3>
                <div class="email-list" id="liveList"></div>
            </div>

            <div class="result-section disabled-section" id="disabledSection">
                <h3>❌ الحسابات المعطلة (Disabled)</h3>
                <div class="email-list" id="disabledList"></div>
            </div>

            <div class="result-section error-section" id="errorSection">
                <h3>⚠️ حسابات خطأ / غير موجودة</h3>
                <div class="email-list" id="errorList"></div>
            </div>
        </div>

        <footer>⚡ فحص سريع باستخدام خوادم Google MX | نتائج دقيقة</footer>
    </div>

    <script>
        async function startVerification() {
            const emailsInput = document.getElementById('emailsInput').value;
            if (!emailsInput.trim()) {
                alert('الرجاء إدخال حسابات Gmail');
                return;
            }

            const emails = emailsInput.split('\\n').filter(e => e.trim() && e.includes('@'));
            
            if (emails.length === 0) {
                alert('الرجاء إدخال حسابات صالحة');
                return;
            }

            document.getElementById('verifyBtn').disabled = true;
            document.getElementById('verifyBtn').innerHTML = '<span class="loading"></span> جاري الفحص...';
            document.getElementById('progress').classList.add('show');
            document.getElementById('results').style.display = 'none';

            const response = await fetch('/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ emails: emails })
            });

            const result = await response.json();
            displayResults(result);
        }

        function displayResults(result) {
            document.getElementById('verifyBtn').disabled = false;
            document.getElementById('verifyBtn').innerHTML = '🔎 بدء الفحص';
            document.getElementById('progress').classList.remove('show');
            document.getElementById('results').style.display = 'block';

            // الإحصائيات
            const statsHtml = `
                <div class="stat-card">
                    <div class="stat-number live-number">${result.live_count}</div>
                    <div class="stat-label">✅ نشط</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number disabled-number">${result.disabled_count}</div>
                    <div class="stat-label">❌ معطل</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number error-number">${result.error_count}</div>
                    <div class="stat-label">⚠️ خطأ</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${result.total}</div>
                    <div class="stat-label">📊 الإجمالي</div>
                </div>
            `;
            document.getElementById('stats').innerHTML = statsHtml;

            // الحسابات النشطة
            const liveHtml = result.live.map(email => `<div class="email-item">✅ ${email}</div>`).join('');
            document.getElementById('liveList').innerHTML = liveHtml || '<div class="email-item">لا توجد حسابات نشطة</div>';
            document.getElementById('liveSection').style.display = result.live.length > 0 ? 'block' : 'none';

            // الحسابات المعطلة
            const disabledHtml = result.disabled.map(email => `<div class="email-item">❌ ${email}</div>`).join('');
            document.getElementById('disabledList').innerHTML = disabledHtml || '<div class="email-item">لا توجد حسابات معطلة</div>';
            document.getElementById('disabledSection').style.display = result.disabled.length > 0 ? 'block' : 'none';

            // الأخطاء
            const errorHtml = result.errors.map(email => `<div class="email-item">⚠️ ${email}</div>`).join('');
            document.getElementById('errorList').innerHTML = errorHtml || '<div class="email-item">لا توجد أخطاء</div>';
            document.getElementById('errorSection').style.display = result.errors.length > 0 ? 'block' : 'none';
        }
    </script>
</body>
</html>
'''

# ============================================
# دوال الفحص
# ============================================

def verify_email(email, mx_server):
    """فحص حساب واحد"""
    server = None
    try:
        server = smtplib.SMTP(timeout=SOCKET_TIMEOUT)
        server.connect(mx_server, 25)
        server.helo('gmail.com')
        server.mail('verify@gmail.com')

        code, message = server.rcpt(email)
        server.quit()

        if code == 250:
            return 'live'
        elif code == 550:
            msg = str(message).lower()
            if 'disabled' in msg or 'user disabled' in msg:
                return 'disabled'
            else:
                return 'invalid'
        else:
            return 'error'
    except Exception as e:
        return 'error'
    finally:
        if server:
            try:
                server.quit()
            except:
                pass

def verify_emails_batch(emails):
    """فحص مجموعة من الإيميلات"""
    results = {
        'live': [],
        'disabled': [],
        'errors': [],
        'live_count': 0,
        'disabled_count': 0,
        'error_count': 0,
        'total': len(emails)
    }
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for email in emails:
            mx_server = MX_SERVERS[0]  # استخدام الخادم الأول
            future = executor.submit(verify_email, email, mx_server)
            futures[future] = email
        
        for future in concurrent.futures.as_completed(futures):
            email = futures[future]
            try:
                status = future.result(timeout=10)
                if status == 'live':
                    results['live'].append(email)
                    results['live_count'] += 1
                elif status == 'disabled':
                    results['disabled'].append(email)
                    results['disabled_count'] += 1
                else:
                    results['errors'].append(email)
                    results['error_count'] += 1
            except Exception:
                results['errors'].append(email)
                results['error_count'] += 1
    
    return results

# ============================================
# Routes
# ============================================

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    emails = data.get('emails', [])
    
    # تنظيف الإيميلات
    clean_emails = []
    for email in emails:
        email = email.strip().lower()
        if email and '@gmail.com' in email:
            clean_emails.append(email)
    
    if not clean_emails:
        return jsonify({'error': 'No valid emails provided'}), 400
    
    # فحص الإيميلات
    results = verify_emails_batch(clean_emails)
    
    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
