from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db, init_db
from datetime import datetime, date, timedelta
import json
import io
import os

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'pmpms_nigeria_2024_secret_key'

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' not in session:
        return None
    db = get_db()
    user = db.execute("SELECT u.*, b.name as branch_name, z.name as zone_name FROM users u LEFT JOIN branches b ON u.branch_id=b.id LEFT JOIN zones z ON u.zone_id=z.id WHERE u.id=?", (session['user_id'],)).fetchone()
    db.close()
    return user

def build_where_clause(user, table_alias=None):
    prefix = f"{table_alias}." if table_alias else ''
    role = user['role']
    if role == 'rm':
        return f"{prefix}rm_id = {user['id']}", {}
    elif role == 'branch_head':
        return f"{prefix}branch_id = {user['branch_id']}", {}
    elif role == 'zonal_head':
        db = get_db()
        branches = db.execute("SELECT id FROM branches WHERE zone_id=?", (user['zone_id'],)).fetchall()
        db.close()
        ids = ','.join(str(b['id']) for b in branches)
        return f"{prefix}branch_id IN ({ids})", {}
    else:  # md
        return "1=1", {}

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['full_name']
            return redirect(url_for('dashboard'))
        error = 'Invalid credentials. Please try again.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    return render_template('dashboard.html', user=user)

# ==================== API ROUTES ====================

@app.route('/api/dashboard/summary')
@login_required
def api_dashboard_summary():
    user = get_current_user()
    where, _ = build_where_clause(user)
    db = get_db()
    today = date.today()

    # Total liabilities
    total_liab = db.execute(f"SELECT COALESCE(SUM(balance),0) as total FROM cabal WHERE {where}").fetchone()['total']
    
    # Total loans outstanding
    total_loans = db.execute(f"SELECT COALESCE(SUM(outstanding_balance),0) as total FROM loans WHERE {where} AND status != 'paid'").fetchone()['total']
    
    # Overdue loans
    overdue_loans = db.execute(f"SELECT COUNT(*) as cnt FROM loans WHERE {where} AND status='overdue'").fetchone()['cnt']
    
    # Loans due in 3 days
    due_soon = db.execute(f"SELECT COUNT(*) as cnt FROM loans WHERE {where} AND status='active' AND repayment_date <= date('now', '+3 days') AND repayment_date >= date('now')").fetchone()['cnt']
    
    # Digital banking counts
    digital_active = db.execute(f"SELECT COUNT(*) as cnt FROM digital_banking WHERE {where} AND status='active'").fetchone()['cnt']
    
    # Collections this month
    collections = db.execute(f"SELECT COALESCE(SUM(amount),0) as total FROM collections WHERE {where} AND collection_type='received' AND strftime('%Y-%m', collection_date)=strftime('%Y-%m', 'now')").fetchone()['total']
    
    # Credit card overdue
    credit_overdue = db.execute(f"SELECT COUNT(*) as cnt FROM cards WHERE {where} AND card_type='credit' AND is_overdue=1").fetchone()['cnt']
    
    # Public sector balance
    public_bal = db.execute(f"SELECT COALESCE(SUM(balance),0) as total FROM public_sector WHERE {where}").fetchone()['total']
    
    # Trade dormant
    trade_dormant = db.execute(f"SELECT COUNT(*) as cnt FROM trade_services WHERE {where} AND status='dormant'").fetchone()['cnt']
    
    # Retail accounts
    retail_total = db.execute(f"SELECT COUNT(*) as cnt FROM retail WHERE {where}").fetchone()['cnt']
    retail_active = db.execute(f"SELECT COUNT(*) as cnt FROM retail WHERE {where} AND status='active'").fetchone()['cnt']

    inactive_cabal = db.execute(f"SELECT COUNT(*) as cnt FROM cabal WHERE {where} AND status != 'active'").fetchone()['cnt']
    
    # ========== NEW METRICS ==========
    # 1. New Accounts (MTD) – from CABAL (created_at) and Retail (opened_date)
    new_accounts = db.execute(f"""
        SELECT COUNT(*) as cnt FROM (
            SELECT id FROM cabal WHERE {where} AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            UNION ALL
            SELECT id FROM retail WHERE {where} AND strftime('%Y-%m', opened_date) = strftime('%Y-%m', 'now')
        )
    """).fetchone()['cnt']
    
    # 2. Trade Volume – sum of trade amounts converted to NGN (USD * 1500, others as is)
    trade_volume = db.execute(f"""
        SELECT COALESCE(SUM(
            CASE 
                WHEN currency = 'USD' THEN amount * 1500
                WHEN currency = 'GBP' THEN amount * 2000
                WHEN currency = 'EUR' THEN amount * 1800
                ELSE amount
            END
        ), 0) as total
        FROM trade_services WHERE {where}
    """).fetchone()['total']
    
    # 3. Active NXP – count of pending/approved NXP applications
    # First check if nxp_tracker table exists (to avoid errors if not yet created)
    try:
        nxp_active = db.execute(f"""
            SELECT COUNT(*) as cnt FROM nxp_tracker 
            WHERE {where} AND status IN ('pending', 'approved')
        """).fetchone()['cnt']
    except:
        nxp_active = 0
    
    # Alerts (unchanged)
    alerts = []
    
    overdue_list = db.execute(f"SELECT customer_name, loan_type, outstanding_balance, days_overdue, repayment_date FROM loans WHERE {where} AND status='overdue' ORDER BY days_overdue DESC LIMIT 5").fetchall()
    for loan in overdue_list:
        alerts.append({'type': 'danger', 'icon': '⚠️', 'message': f"Overdue Loan: {loan['customer_name']} - ₦{loan['outstanding_balance']:,.0f} ({loan['days_overdue']} days overdue)"})
    
    due_soon_list = db.execute(f"SELECT customer_name, loan_type, outstanding_balance, repayment_date FROM loans WHERE {where} AND status='active' AND repayment_date <= date('now', '+3 days') AND repayment_date >= date('now')").fetchall()
    for loan in due_soon_list:
        alerts.append({'type': 'warning', 'icon': '🔔', 'message': f"Loan Due Soon: {loan['customer_name']} - ₦{loan['outstanding_balance']:,.0f} due {loan['repayment_date']}"})
    
    cc_overdue_list = db.execute(f"SELECT customer_name, outstanding_balance, days_overdue FROM cards WHERE {where} AND card_type='credit' AND is_overdue=1 LIMIT 3").fetchall()
    for card in cc_overdue_list:
        alerts.append({'type': 'warning', 'icon': '💳', 'message': f"Credit Card Overdue: {card['customer_name']} - ₦{card['outstanding_balance']:,.0f} ({card['days_overdue']} days)"})
    
    dormant_trade = db.execute(f"SELECT customer_name, service_type, expiry_date FROM trade_services WHERE {where} AND status='dormant' LIMIT 3").fetchall()
    for t in dormant_trade:
        alerts.append({'type': 'info', 'icon': '📋', 'message': f"Dormant Trade: {t['customer_name']} - {t['service_type'].replace('_',' ').title()} (Expired: {t['expiry_date']})"})

    db.close()

    return jsonify({
        'total_liabilities': total_liab,
        'total_loans': total_loans,
        'overdue_loans': overdue_loans,
        'loans_due_soon': due_soon,
        'digital_active': digital_active,
        'collections_mtd': collections,
        'credit_card_overdue': credit_overdue,
        'public_sector_balance': public_bal,
        'trade_dormant': trade_dormant,
        'retail_total': retail_total,
        'retail_active': retail_active,
        'inactive_cabal': inactive_cabal,
        'new_accounts': new_accounts,
        'trade_volume': trade_volume,
        'nxp_active': nxp_active,
        'alerts': alerts
    })

@app.route('/api/cabal')
@login_required
def api_cabal():
    user = get_current_user()
    # For main query with JOINs, use alias 'c'
    where_rows, _ = build_where_clause(user, table_alias='c')
    # For summary query on single table, no alias
    where_summary, _ = build_where_clause(user, table_alias=None)
    db = get_db()
    
    rows = db.execute(f"""
        SELECT c.*, u.full_name as rm_name, b.name as branch_name
        FROM cabal c
        JOIN users u ON c.rm_id = u.id
        JOIN branches b ON c.branch_id = b.id
        WHERE {where_rows} ORDER BY c.balance DESC
    """).fetchall()
    
    summary = db.execute(f"""
        SELECT account_type, COUNT(*) as count, SUM(balance) as total, status
        FROM cabal WHERE {where_summary} GROUP BY account_type, status
    """).fetchall()
    
    db.close()
    return jsonify({
        'data': [dict(r) for r in rows],
        'summary': [dict(s) for s in summary]
    })
    
@app.route('/api/loans')
@login_required
def api_loans():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='l')
    db = get_db()
    
    rows = db.execute(f"""
        SELECT l.*, u.full_name as rm_name, b.name as branch_name
        FROM loans l
        JOIN users u ON l.rm_id = u.id
        JOIN branches b ON l.branch_id = b.id
        WHERE {where} ORDER BY l.status ASC, l.days_overdue DESC
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})


@app.route('/api/trade')
@login_required
def api_trade():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='t')
    db = get_db()
    
    rows = db.execute(f"""
        SELECT t.*, u.full_name as rm_name, b.name as branch_name
        FROM trade_services t
        JOIN users u ON t.rm_id = u.id
        JOIN branches b ON t.branch_id = b.id
        WHERE {where} ORDER BY t.status, t.created_at DESC
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})

@app.route('/api/digital')
@login_required
def api_digital():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='d')
    db = get_db()
    
    rows = db.execute(f"""
        SELECT d.*, u.full_name as rm_name, b.name as branch_name
        FROM digital_banking d
        JOIN users u ON d.rm_id = u.id
        JOIN branches b ON d.branch_id = b.id
        WHERE {where} ORDER BY d.product_type, d.status
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})

@app.route('/api/cards')
@login_required
def api_cards():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='c')
    db = get_db()
    
    rows = db.execute(f"""
        SELECT c.*, u.full_name as rm_name, b.name as branch_name
        FROM cards c
        JOIN users u ON c.rm_id = u.id
        JOIN branches b ON c.branch_id = b.id
        WHERE {where} ORDER BY c.is_overdue DESC, c.days_overdue DESC
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})


@app.route('/api/retail')
@login_required
def api_retail():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='r')
    db = get_db()
    
    rows = db.execute(f"""
        SELECT r.*, u.full_name as rm_name, b.name as branch_name
        FROM retail r
        JOIN users u ON r.rm_id = u.id
        JOIN branches b ON r.branch_id = b.id
        WHERE {where} ORDER BY r.status, r.balance DESC
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})

@app.route('/api/collections')
@login_required
def api_collections():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='col')   # add alias
    db = get_db()
    
    rows = db.execute(f"""
        SELECT col.*, u.full_name as rm_name, b.name as branch_name
        FROM collections col
        JOIN users u ON col.rm_id = u.id
        JOIN branches b ON col.branch_id = b.id
        WHERE {where} ORDER BY col.collection_date DESC
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})

@app.route('/api/public_sector')
@login_required
def api_public_sector():
    user = get_current_user()
    where, _ = build_where_clause(user, table_alias='ps')
    db = get_db()
    
    rows = db.execute(f"""
        SELECT ps.*, u.full_name as rm_name, b.name as branch_name
        FROM public_sector ps
        JOIN users u ON ps.rm_id = u.id
        JOIN branches b ON ps.branch_id = b.id
        WHERE {where} ORDER BY ps.balance DESC
    """).fetchall()
    
    db.close()
    return jsonify({'data': [dict(r) for r in rows]})

@app.route('/api/projections')
@login_required
def api_projections():
    user = get_current_user()
    where, _ = build_where_clause(user)
    db = get_db()
    today = date.today()
    
    # Current liabilities trend (last 6 months simulated from current)
    total_liab = db.execute(f"SELECT COALESCE(SUM(balance),0) as total FROM cabal WHERE {where}").fetchone()['total']
    total_loans = db.execute(f"SELECT COALESCE(SUM(outstanding_balance),0) as total FROM loans WHERE {where} AND status != 'paid'").fetchone()['total']
    collections_total = db.execute(f"SELECT COALESCE(SUM(amount),0) as total FROM collections WHERE {where} AND collection_type='received'").fetchone()['total']
    
    # Simple projection: linear growth model based on current values
    import random
    growth_rate_monthly = 0.035  # 3.5% monthly growth assumed
    
    months = []
    liab_proj = []
    loan_proj = []
    col_proj = []
    
    for i in range(-2, 4):  # -2 past months, current, 3 future
        m = (today.month + i - 1) % 12 + 1
        y = today.year + (today.month + i - 1) // 12
        months.append(f"{y}-{m:02d}")
        factor = (1 + growth_rate_monthly) ** i
        liab_proj.append(round(total_liab * factor * (1 + random.uniform(-0.02, 0.02)), 0))
        loan_proj.append(round(total_loans * factor * (1 + random.uniform(-0.03, 0.03)), 0))
        col_proj.append(round(collections_total / 3 * factor * (1 + random.uniform(-0.05, 0.05)), 0))
    
    # Quarter projections
    q_current = (today.month - 1) // 3 + 1
    quarters = [f"Q{((q_current + i - 1) % 4) + 1} {today.year + (q_current + i - 1) // 4}" for i in range(4)]
    q_liab = [round(total_liab * (1 + growth_rate_monthly * 3) ** i, 0) for i in range(4)]
    
    # Year end projection
    months_remaining = 12 - today.month
    year_end_liab = round(total_liab * (1 + growth_rate_monthly) ** months_remaining, 0)
    year_end_loans = round(total_loans * (1 + growth_rate_monthly) ** months_remaining, 0)
    
    db.close()
    return jsonify({
        'monthly': {'labels': months, 'liabilities': liab_proj, 'loans': loan_proj, 'collections': col_proj},
        'quarterly': {'labels': quarters, 'liabilities': q_liab},
        'year_end': {'liabilities': year_end_liab, 'loans': year_end_loans, 'current_liabilities': total_liab, 'current_loans': total_loans}
    })

@app.route('/api/targets', methods=['GET', 'POST'])
@login_required
def api_targets():
    user = get_current_user()
    db = get_db()
    today = date.today()
    
    if request.method == 'POST':
        data = request.json
        # Only branch_head, zonal_head, md can set targets
        if user['role'] not in ['branch_head', 'zonal_head', 'md', 'rm']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.execute("""INSERT OR REPLACE INTO targets 
            (entity_type, entity_id, metric, period, year, period_value, target_value)
            VALUES (?,?,?,?,?,?,?)""",
            (data['entity_type'], data['entity_id'], data['metric'], 
             data['period'], data['year'], data['period_value'], data['target_value']))
        db.commit()
        db.close()
        return jsonify({'success': True})
    
    # GET - fetch targets for current user context
    if user['role'] == 'rm':
        targets = db.execute("SELECT * FROM targets WHERE entity_type='rm' AND entity_id=? AND year=?", (user['id'], today.year)).fetchall()
    elif user['role'] == 'branch_head':
        targets = db.execute("SELECT * FROM targets WHERE entity_type='branch' AND entity_id=? AND year=?", (user['branch_id'], today.year)).fetchall()
        if not targets:
            targets = db.execute("SELECT * FROM targets WHERE entity_type='rm' AND entity_id IN (SELECT id FROM users WHERE branch_id=?) AND year=?", (user['branch_id'], today.year)).fetchall()
    else:
        targets = db.execute("SELECT * FROM targets WHERE year=?", (today.year,)).fetchall()
    
    db.close()
    return jsonify({'data': [dict(t) for t in targets]})

@app.route('/api/hierarchy')
@login_required
def api_hierarchy():
    """Returns the top-level items the current user should see first."""
    user = get_current_user()
    db = get_db()

    def zone_summary(zone_id):
        branch_ids = [r['id'] for r in db.execute("SELECT id FROM branches WHERE zone_id=?", (zone_id,)).fetchall()]
        if not branch_ids:
            return {'liabilities': 0, 'loans': 0, 'branches': 0, 'rms': 0}
        ids = ','.join(str(i) for i in branch_ids)
        liab = db.execute(f"SELECT COALESCE(SUM(balance),0) as t FROM cabal WHERE branch_id IN ({ids})").fetchone()['t']
        loans = db.execute(f"SELECT COALESCE(SUM(outstanding_balance),0) as t FROM loans WHERE branch_id IN ({ids}) AND status!='paid'").fetchone()['t']
        rms = db.execute(f"SELECT COUNT(*) as t FROM users WHERE role='rm' AND branch_id IN ({ids})").fetchone()['t']
        return {'liabilities': liab, 'loans': loans, 'branches': len(branch_ids), 'rms': rms}

    def branch_summary(branch_id):
        liab = db.execute("SELECT COALESCE(SUM(balance),0) as t FROM cabal WHERE branch_id=?", (branch_id,)).fetchone()['t']
        loans = db.execute("SELECT COALESCE(SUM(outstanding_balance),0) as t FROM loans WHERE branch_id=? AND status!='paid'", (branch_id,)).fetchone()['t']
        overdue = db.execute("SELECT COUNT(*) as t FROM loans WHERE branch_id=? AND status='overdue'", (branch_id,)).fetchone()['t']
        rms = db.execute("SELECT COUNT(*) as t FROM users WHERE role='rm' AND branch_id=?", (branch_id,)).fetchone()['t']
        digital = db.execute("SELECT COUNT(*) as t FROM digital_banking WHERE branch_id=? AND status='active'", (branch_id,)).fetchone()['t']
        return {'liabilities': liab, 'loans': loans, 'overdue_loans': overdue, 'rms': rms, 'digital_active': digital}

    if user['role'] == 'md':
        zones = db.execute("SELECT * FROM zones").fetchall()
        result = {'level': 'zones', 'items': []}
        for z in zones:
            s = zone_summary(z['id'])
            result['items'].append({**dict(z), **s, 'type': 'zone'})

    elif user['role'] == 'zonal_head':
        branches = db.execute("SELECT b.*, z.name as zone_name FROM branches b JOIN zones z ON b.zone_id=z.id WHERE b.zone_id=?", (user['zone_id'],)).fetchall()
        result = {'level': 'branches', 'zone_id': user['zone_id'], 'items': []}
        for b in branches:
            s = branch_summary(b['id'])
            result['items'].append({**dict(b), **s, 'type': 'branch'})

    elif user['role'] == 'branch_head':
        rms = db.execute("SELECT u.id, u.full_name, u.branch_id, b.name as branch_name FROM users u JOIN branches b ON u.branch_id=b.id WHERE u.role='rm' AND u.branch_id=?", (user['branch_id'],)).fetchall()
        result = {'level': 'rms', 'branch_id': user['branch_id'], 'items': []}
        for r in rms:
            where = f"rm_id={r['id']}"
            liab = db.execute(f"SELECT COALESCE(SUM(balance),0) as t FROM cabal WHERE {where}").fetchone()['t']
            loans = db.execute(f"SELECT COALESCE(SUM(outstanding_balance),0) as t FROM loans WHERE {where} AND status!='paid'").fetchone()['t']
            overdue = db.execute(f"SELECT COUNT(*) as t FROM loans WHERE {where} AND status='overdue'").fetchone()['t']
            digital = db.execute(f"SELECT COUNT(*) as t FROM digital_banking WHERE {where} AND status='active'").fetchone()['t']
            result['items'].append({**dict(r), 'type': 'rm', 'liabilities': liab, 'loans': loans, 'overdue_loans': overdue, 'digital_active': digital})
    else:
        result = {'level': 'none', 'items': []}

    db.close()
    return jsonify(result)


@app.route('/api/hierarchy/zone/<int:zone_id>/branches')
@login_required
def api_zone_branches(zone_id):
    """Branches inside a zone with their summaries."""
    db = get_db()
    branches = db.execute("SELECT b.*, z.name as zone_name FROM branches b JOIN zones z ON b.zone_id=z.id WHERE b.zone_id=?", (zone_id,)).fetchall()
    items = []
    for b in branches:
        liab = db.execute("SELECT COALESCE(SUM(balance),0) as t FROM cabal WHERE branch_id=?", (b['id'],)).fetchone()['t']
        loans = db.execute("SELECT COALESCE(SUM(outstanding_balance),0) as t FROM loans WHERE branch_id=? AND status!='paid'", (b['id'],)).fetchone()['t']
        overdue = db.execute("SELECT COUNT(*) as t FROM loans WHERE branch_id=? AND status='overdue'", (b['id'],)).fetchone()['t']
        rms = db.execute("SELECT COUNT(*) as t FROM users WHERE role='rm' AND branch_id=?", (b['id'],)).fetchone()['t']
        digital = db.execute("SELECT COUNT(*) as t FROM digital_banking WHERE branch_id=? AND status='active'", (b['id'],)).fetchone()['t']
        items.append({**dict(b), 'type': 'branch', 'liabilities': liab, 'loans': loans, 'overdue_loans': overdue, 'rms': rms, 'digital_active': digital})
    db.close()
    return jsonify({'level': 'branches', 'zone_id': zone_id, 'items': items})


@app.route('/api/hierarchy/branch/<int:branch_id>/rms')
@login_required
def api_branch_rms(branch_id):
    """RMs inside a branch with their performance summaries."""
    db = get_db()
    branch = db.execute("SELECT b.*, z.name as zone_name FROM branches b JOIN zones z ON b.zone_id=z.id WHERE b.id=?", (branch_id,)).fetchone()
    rms = db.execute("SELECT u.id, u.full_name, u.branch_id FROM users u WHERE u.role='rm' AND u.branch_id=?", (branch_id,)).fetchall()
    items = []
    for r in rms:
        where = f"rm_id={r['id']}"
        liab = db.execute(f"SELECT COALESCE(SUM(balance),0) as t FROM cabal WHERE {where}").fetchone()['t']
        loans = db.execute(f"SELECT COALESCE(SUM(outstanding_balance),0) as t FROM loans WHERE {where} AND status!='paid'").fetchone()['t']
        overdue = db.execute(f"SELECT COUNT(*) as t FROM loans WHERE {where} AND status='overdue'").fetchone()['t']
        digital = db.execute(f"SELECT COUNT(*) as t FROM digital_banking WHERE {where} AND status='active'").fetchone()['t']
        collections = db.execute(f"SELECT COALESCE(SUM(amount),0) as t FROM collections WHERE {where} AND collection_type='received'").fetchone()['t']
        retail = db.execute(f"SELECT COUNT(*) as t FROM retail WHERE {where}").fetchone()['t']
        items.append({**dict(r), 'type': 'rm', 'liabilities': liab, 'loans': loans,
                      'overdue_loans': overdue, 'digital_active': digital, 'collections': collections, 'retail': retail})
    db.close()
    return jsonify({'level': 'rms', 'branch_id': branch_id, 'branch': dict(branch) if branch else {}, 'items': items})


@app.route('/api/rm_detail/<int:rm_id>')
@login_required
def api_rm_detail(rm_id):
    """Full portfolio detail for a specific RM — all modules."""
    db = get_db()
    rm = db.execute("SELECT u.*, b.name as branch_name, z.name as zone_name FROM users u JOIN branches b ON u.branch_id=b.id JOIN zones z ON b.zone_id=z.id WHERE u.id=?", (rm_id,)).fetchone()
    if not rm:
        return jsonify({'error': 'Not found'}), 404

    w = f"rm_id={rm_id}"

    cabal = db.execute(f"SELECT * FROM cabal WHERE {w} ORDER BY balance DESC").fetchall()
    loans = db.execute(f"SELECT * FROM loans WHERE {w} ORDER BY status, days_overdue DESC").fetchall()
    trade = db.execute(f"SELECT * FROM trade_services WHERE {w} ORDER BY status").fetchall()
    digital = db.execute(f"SELECT * FROM digital_banking WHERE {w} ORDER BY product_type").fetchall()
    cards = db.execute(f"SELECT * FROM cards WHERE {w} ORDER BY is_overdue DESC").fetchall()
    retail = db.execute(f"SELECT * FROM retail WHERE {w} ORDER BY balance DESC").fetchall()
    collections = db.execute(f"SELECT * FROM collections WHERE {w} ORDER BY collection_date DESC").fetchall()
    public_sector = db.execute(f"SELECT * FROM public_sector WHERE {w} ORDER BY balance DESC").fetchall()

    # KPI summary
    total_liab = sum(r['balance'] for r in cabal)
    total_loans = sum(r['outstanding_balance'] for r in loans if r['status'] != 'paid')
    overdue_loans = sum(1 for r in loans if r['status'] == 'overdue')
    digital_active = sum(1 for r in digital if r['status'] == 'active')
    collections_total = sum(r['amount'] for r in collections if r['collection_type'] == 'received')
    credit_overdue = sum(1 for r in cards if r['is_overdue'])
    ps_balance = sum(r['balance'] for r in public_sector)

    db.close()
    return jsonify({
        'rm': dict(rm),
        'summary': {
            'total_liabilities': total_liab, 'total_loans': total_loans,
            'overdue_loans': overdue_loans, 'digital_active': digital_active,
            'collections': collections_total, 'credit_overdue': credit_overdue,
            'public_sector_balance': ps_balance, 'retail_count': len(retail)
        },
        'cabal': [dict(r) for r in cabal],
        'loans': [dict(r) for r in loans],
        'trade': [dict(r) for r in trade],
        'digital': [dict(r) for r in digital],
        'cards': [dict(r) for r in cards],
        'retail': [dict(r) for r in retail],
        'collections': [dict(r) for r in collections],
        'public_sector': [dict(r) for r in public_sector],
    })

@app.route('/api/export/<module>')
@login_required
def api_export(module):
    user = get_current_user()
    
    # Map each module to the table alias used in the SQL query
    alias_map = {
        'cabal': 'c',
        'loans': 'l',
        'trade': 't',
        'digital': 'd',
        'cards': 'c',
        'retail': 'r',
        'collections': 'col',
        'public_sector': 'ps',
    }
    
    if module not in alias_map:
        return jsonify({'error': 'Invalid module'}), 400
    
    alias = alias_map[module]
    
    # Allow override by rm_id for hierarchy drill-down exports
    rm_id_override = request.args.get('rm_id', type=int)
    if rm_id_override:
        # Qualified condition to avoid ambiguity
        where = f"{alias}.rm_id = {rm_id_override}"
    else:
        where, _ = build_where_clause(user, table_alias=alias)
    
    db = get_db()
    
    queries = {
        'cabal': f"SELECT c.customer_name, c.account_number, c.account_type, c.balance, c.currency, c.status, c.last_transaction_date, u.full_name as rm, b.name as branch FROM cabal c JOIN users u ON c.rm_id=u.id JOIN branches b ON c.branch_id=b.id WHERE {where}",
        'loans': f"SELECT l.customer_name, l.account_number, l.loan_type, l.outstanding_balance, l.original_amount, l.repayment_date, l.status, l.days_overdue, u.full_name as rm, b.name as branch FROM loans l JOIN users u ON l.rm_id=u.id JOIN branches b ON l.branch_id=b.id WHERE {where}",
        'trade': f"SELECT t.customer_name, t.reference, t.service_type, t.amount, t.currency, t.status, t.expiry_date, u.full_name as rm, b.name as branch FROM trade_services t JOIN users u ON t.rm_id=u.id JOIN branches b ON t.branch_id=b.id WHERE {where}",
        'digital': f"SELECT d.customer_name, d.account_number, d.product_type, d.status, d.terminal_id, d.issued_date, d.last_activity_date, u.full_name as rm, b.name as branch FROM digital_banking d JOIN users u ON d.rm_id=u.id JOIN branches b ON d.branch_id=b.id WHERE {where}",
        'cards': f"SELECT c.customer_name, c.account_number, c.card_type, c.status, c.credit_limit, c.outstanding_balance, c.payment_due_date, c.is_overdue, c.days_overdue, u.full_name as rm, b.name as branch FROM cards c JOIN users u ON c.rm_id=u.id JOIN branches b ON c.branch_id=b.id WHERE {where}",
        'retail': f"SELECT r.customer_name, r.account_number, r.account_type, r.balance, r.status, r.opened_date, r.last_transaction_date, u.full_name as rm, b.name as branch FROM retail r JOIN users u ON r.rm_id=u.id JOIN branches b ON r.branch_id=b.id WHERE {where}",
        'collections': f"SELECT col.customer_name, col.account_number, col.collection_type, col.amount, col.collection_date, u.full_name as rm, b.name as branch FROM collections col JOIN users u ON col.rm_id=u.id JOIN branches b ON col.branch_id=b.id WHERE {where}",
        'public_sector': f"SELECT ps.institution_name, ps.account_number, ps.sector_type, ps.balance, ps.status, ps.opened_date, u.full_name as rm, b.name as branch FROM public_sector ps JOIN users u ON ps.rm_id=u.id JOIN branches b ON ps.branch_id=b.id WHERE {where}",
    }
    
    rows = db.execute(queries[module]).fetchall()
    db.close()
    
    if not EXCEL_AVAILABLE:
        # CSV fallback
        import csv
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name=f'{module}_export.csv')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = module.replace('_', ' ').title()
    
    header_fill = PatternFill(start_color='003366', end_color='003366', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    
    if rows:
        headers = list(rows[0].keys())
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header.replace('_', ' ').upper())
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        for row_idx, row in enumerate(rows, 2):
            for col_idx, value in enumerate(dict(row).values(), 1):
                ws.cell(row=row_idx, column=col_idx, value=value)
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                     as_attachment=True, download_name=f'{module}_export_{date.today()}.xlsx')
    
    
@app.route('/api/rm_performance/<int:rm_id>')
@login_required
def api_rm_performance(rm_id):
    user = get_current_user()
    db = get_db()
    
    rm = db.execute("SELECT id, full_name, branch_id FROM users WHERE id=? AND role='rm'", (rm_id,)).fetchone()
    if not rm:
        return jsonify({'error': 'RM not found'}), 404
    
    where = f"rm_id = {rm_id}"
    
    liab = db.execute(f"SELECT COALESCE(SUM(balance),0) as t FROM cabal WHERE {where}").fetchone()['t']
    loans = db.execute(f"SELECT COALESCE(SUM(outstanding_balance),0) as t FROM loans WHERE {where} AND status != 'paid'").fetchone()['t']
    digital = db.execute(f"SELECT COUNT(*) as t FROM digital_banking WHERE {where} AND status='active'").fetchone()['t']
    collections = db.execute(f"SELECT COALESCE(SUM(amount),0) as t FROM collections WHERE {where} AND collection_type='received'").fetchone()['t']
    retail = db.execute(f"SELECT COUNT(*) as t FROM retail WHERE {where}").fetchone()['t']
    
    targets = db.execute("SELECT * FROM targets WHERE entity_type='rm' AND entity_id=?", (rm_id,)).fetchall()
    target_map = {f"{t['metric']}_{t['period']}": t['target_value'] for t in targets}
    
    db.close()
    return jsonify({
        'rm': dict(rm),
        'metrics': {
            'total_liabilities': liab, 'total_loans': loans,
            'digital_active': digital, 'collections': collections, 'retail_accounts': retail
        },
        'targets': target_map
    })
    
    
@app.route('/api/projections/detailed')
@login_required
def api_projections_detailed():
    user = get_current_user()
    where, _ = build_where_clause(user)
    db = get_db()
    today = date.today()

    # Get current balances per account type from CABAL
    cabal_data = db.execute(f"""
        SELECT account_type, SUM(balance) as total
        FROM cabal
        WHERE {where}
        GROUP BY account_type
    """).fetchall()

    balances = {
        'current': 0,
        'savings': 0,
        'fixed_deposit': 0,
        'fx': 0,  # sum of fx_dollar, fx_pounds, fx_euro
    }
    for row in cabal_data:
        atype = row['account_type']
        if atype == 'current':
            balances['current'] = row['total']
        elif atype == 'savings':
            balances['savings'] = row['total']
        elif atype == 'fixed_deposit':
            balances['fixed_deposit'] = row['total']
        elif atype in ('fx_dollar', 'fx_pounds', 'fx_euro'):
            balances['fx'] += row['total']

    # Current income (collections this year to date)
    income_current = db.execute(f"""
        SELECT COALESCE(SUM(amount),0) as total
        FROM collections
        WHERE {where} AND collection_type='received'
        AND strftime('%Y', collection_date) = strftime('%Y', 'now')
    """).fetchone()['total']

    # Monthly growth assumptions (business logic)
    growth_rates = {
        'current': 0.025,   # 2.5% per month
        'savings': 0.018,   # 1.8%
        'fixed_deposit': 0.012,  # 1.2%
        'fx': 0.032,        # 3.2% (FX volatility)
        'income': 0.028,    # 2.8% monthly growth in collections
    }

    # Generate monthly projections for next 6 months
    months = []
    current_proj = []
    savings_proj = []
    fixed_proj = []
    fx_proj = []
    income_proj = []

    for i in range(1, 7):  # next 6 months
        m = (today.month + i - 1) % 12 + 1
        y = today.year + (today.month + i - 1) // 12
        months.append(f"{y}-{m:02d}")
        factor_current = (1 + growth_rates['current']) ** i
        factor_savings = (1 + growth_rates['savings']) ** i
        factor_fixed = (1 + growth_rates['fixed_deposit']) ** i
        factor_fx = (1 + growth_rates['fx']) ** i
        factor_income = (1 + growth_rates['income']) ** i

        current_proj.append(round(balances['current'] * factor_current, 0))
        savings_proj.append(round(balances['savings'] * factor_savings, 0))
        fixed_proj.append(round(balances['fixed_deposit'] * factor_fixed, 0))
        fx_proj.append(round(balances['fx'] * factor_fx, 0))
        income_proj.append(round(income_current / 6 * factor_income, 0))  # monthly average

    # Determine focus advice
    growth_pct = {
        'DDA (Current)': growth_rates['current'] * 100,
        'Savings': growth_rates['savings'] * 100,
        'Fixed Deposit': growth_rates['fixed_deposit'] * 100,
        'FX Deposits': growth_rates['fx'] * 100,
        'Income (Collections)': growth_rates['income'] * 100,
    }
    fastest = max(growth_pct, key=growth_pct.get)
    largest_balance = max(balances, key=lambda k: balances.get(k, 0))
    advice = f"📈 {fastest} shows the highest monthly growth rate ({growth_pct[fastest]:.1f}%). Consider allocating more resources to {fastest.lower()}. " \
             f"Also, {largest_balance} constitutes the largest liability base – ensure quality monitoring."

    db.close()
    return jsonify({
        'months': months,
        'current': current_proj,
        'savings': savings_proj,
        'fixed_deposit': fixed_proj,
        'fx': fx_proj,
        'income': income_proj,
        'advice': advice,
        'current_balance': balances['current'],
        'savings_balance': balances['savings'],
        'fixed_balance': balances['fixed_deposit'],
        'fx_balance': balances['fx'],
        'income_ytd': income_current,
        'growth_rates': growth_rates
    })
    

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)