import sqlite3
import os
from datetime import datetime, date, timedelta
import random

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'pmpms.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL, -- rm, branch_head, zonal_head, md
        branch_id INTEGER,
        zone_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Zones
    c.execute('''CREATE TABLE IF NOT EXISTS zones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL
    )''')

    # Branches
    c.execute('''CREATE TABLE IF NOT EXISTS branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        zone_id INTEGER NOT NULL,
        FOREIGN KEY (zone_id) REFERENCES zones(id)
    )''')

    # Targets
    c.execute('''CREATE TABLE IF NOT EXISTS targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL, -- rm, branch, zone, bank
        entity_id INTEGER NOT NULL,
        metric TEXT NOT NULL,
        period TEXT NOT NULL, -- monthly, quarterly, yearly
        year INTEGER NOT NULL,
        period_value INTEGER NOT NULL, -- month 1-12, quarter 1-4, year=0
        target_value REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # CABAL - Liability Products
    c.execute('''CREATE TABLE IF NOT EXISTS cabal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        account_type TEXT NOT NULL, -- current, savings, fixed_deposit, fx_dollar, fx_pounds, fx_euro
        balance REAL DEFAULT 0,
        currency TEXT DEFAULT 'NGN',
        status TEXT DEFAULT 'active', -- active, inactive, dormant
        last_transaction_date DATE,
        created_at DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # LOANS
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        loan_type TEXT NOT NULL, -- term_loan, overdraft, bond, guarantee
        outstanding_balance REAL DEFAULT 0,
        original_amount REAL DEFAULT 0,
        repayment_date DATE,
        status TEXT DEFAULT 'active', -- active, overdue, paid
        days_overdue INTEGER DEFAULT 0,
        created_at DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # TRADE SERVICES
    c.execute('''CREATE TABLE IF NOT EXISTS trade_services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        reference TEXT UNIQUE NOT NULL,
        service_type TEXT NOT NULL, -- form_m, form_a, lc, fx_transaction
        amount REAL DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'active', -- active, inactive, dormant, completed
        expiry_date DATE,
        created_at DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # DIGITAL BANKING
    c.execute('''CREATE TABLE IF NOT EXISTS digital_banking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        product_type TEXT NOT NULL, -- mobile_app, pos, internet_banking, ussd
        status TEXT DEFAULT 'active', -- active, inactive, dormant
        terminal_id TEXT,
        issued_date DATE DEFAULT CURRENT_DATE,
        last_activity_date DATE,
        created_at DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # CARDS
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        card_type TEXT NOT NULL, -- debit, credit
        status TEXT DEFAULT 'active', -- active, inactive
        credit_limit REAL DEFAULT 0,
        outstanding_balance REAL DEFAULT 0,
        payment_due_date DATE,
        is_overdue INTEGER DEFAULT 0,
        days_overdue INTEGER DEFAULT 0,
        issued_date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # RETAIL
    c.execute('''CREATE TABLE IF NOT EXISTS retail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        account_type TEXT DEFAULT 'savings',
        balance REAL DEFAULT 0,
        status TEXT DEFAULT 'active', -- active, inactive, dormant
        opened_date DATE DEFAULT CURRENT_DATE,
        last_transaction_date DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # COLLECTIONS
    c.execute('''CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        collection_type TEXT NOT NULL, -- received, paid
        amount REAL DEFAULT 0,
        collection_date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # PUBLIC SECTOR
    c.execute('''CREATE TABLE IF NOT EXISTS public_sector (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        institution_name TEXT NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        sector_type TEXT NOT NULL, -- federal, state, local, parastatal (or Corporate/Government)
        balance REAL DEFAULT 0,
        status TEXT DEFAULT 'active',
        opened_date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    # NXP TRACKER (new)
    c.execute('''CREATE TABLE IF NOT EXISTS nxp_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rm_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        reference TEXT UNIQUE NOT NULL,
        product_description TEXT,
        amount REAL DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'pending',  -- pending, approved, completed
        created_at DATE DEFAULT CURRENT_DATE,
        updated_at DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (rm_id) REFERENCES users(id)
    )''')

    conn.commit()
    conn.close()
    seed_data()
    seed_public_sector_entities()


def seed_data():
    conn = get_db()
    c = conn.cursor()

    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    from werkzeug.security import generate_password_hash

    # Zones
    zones = [('North Zone', 'NZ'), ('South Zone', 'SZ'), ('Lagos Zone', 'LZ')]
    for z in zones:
        c.execute("INSERT INTO zones (name, code) VALUES (?, ?)", z)

    # Branches
    branches = [
        ('Abuja Main Branch', 'ABJ001', 1),
        ('Kano Branch', 'KAN001', 1),
        ('Port Harcourt Branch', 'PHC001', 2),
        ('Ibadan Branch', 'IBD001', 2),
        ('Lagos Island Branch', 'LGI001', 3),
        ('Victoria Island Branch', 'VIS001', 3),
        ('Ikeja Branch', 'IKJ001', 3),
    ]
    for b in branches:
        c.execute("INSERT INTO branches (name, code, zone_id) VALUES (?, ?, ?)", b)

    # Users
    users = [
        ('md_admin', generate_password_hash('password'), 'Dr. Adeyemi Balogun', 'md', None, None),
        ('zonal_north', generate_password_hash('password'), 'Mrs. Fatima Aliyu', 'zonal_head', None, 1),
        ('zonal_south', generate_password_hash('password'), 'Mr. Emeka Obi', 'zonal_head', None, 2),
        ('zonal_lagos', generate_password_hash('password'), 'Mr. Tunde Adesanya', 'zonal_head', None, 3),
        ('bh_abuja', generate_password_hash('password'), 'Mr. Usman Garba', 'branch_head', 1, 1),
        ('bh_vi', generate_password_hash('password'), 'Mrs. Chioma Nwosu', 'branch_head', 6, 3),
        ('bh_ikeja', generate_password_hash('password'), 'Mr. Segun Adebayo', 'branch_head', 7, 3),
        ('rm_ade', generate_password_hash('password'), 'Mr. Adeleke Fashola', 'rm', 6, 3),
        ('rm_bello', generate_password_hash('password'), 'Miss Blessing Bello', 'rm', 6, 3),
        ('rm_chukwu', generate_password_hash('password'), 'Mr. Chukwuemeka Eze', 'rm', 7, 3),
        ('rm_ibrahim', generate_password_hash('password'), 'Mr. Ibrahim Musa', 'rm', 1, 1),
        ('rm_adaeze', generate_password_hash('password'), 'Mrs. Adaeze Okonkwo', 'rm', 3, 2),
    ]
    for u in users:
        c.execute("INSERT INTO users (username, password, full_name, role, branch_id, zone_id) VALUES (?,?,?,?,?,?)", u)

    conn.commit()

    # Get rm ids
    c.execute("SELECT id, branch_id FROM users WHERE role='rm'")
    rms = c.fetchall()

    today = date.today()
    customers = ['Dangote Industries', 'MTN Nigeria', 'Zenith Bank', 'First Bank', 'Access Holdings',
                 'Flour Mills', 'BUA Foods', 'Seplat Energy', 'Airtel Nigeria', 'Guinness Nigeria',
                 'Nestle Nigeria', 'Nigerian Breweries', 'GTCO', 'UBA Plc', 'Stanbic IBTC',
                 'Total Energies', 'Julius Berger', 'Conoil', 'Okomu Oil', 'Transcorp Hotels']

    account_counter = [1000000]
    def next_acct():
        account_counter[0] += 1
        return f"0{account_counter[0]}"

    cabal_types = ['current', 'savings', 'fixed_deposit', 'fx_dollar', 'fx_pounds', 'fx_euro']
    loan_types = ['term_loan', 'overdraft', 'bond', 'guarantee']
    trade_types = ['form_m', 'form_a', 'lc', 'fx_transaction']
    digital_types = ['mobile_app', 'pos', 'internet_banking', 'ussd']

    ref_counter = [1]
    def next_ref(prefix):
        ref_counter[0] += 1
        return f"{prefix}{ref_counter[0]:06d}"

    for rm in rms:
        rm_id, branch_id = rm['id'], rm['branch_id']

        # CABAL
        for i in range(15):
            cust = random.choice(customers) + f" {i+1}"
            acct = next_acct()
            acct_type = random.choice(cabal_types)
            curr = 'USD' if 'fx_dollar' in acct_type else 'GBP' if 'fx_pounds' in acct_type else 'EUR' if 'fx_euro' in acct_type else 'NGN'
            bal = round(random.uniform(100000, 50000000), 2)
            status = random.choice(['active', 'active', 'active', 'inactive', 'dormant'])
            last_txn = today - timedelta(days=random.randint(0, 365))
            c.execute("INSERT INTO cabal (rm_id, branch_id, customer_name, account_number, account_type, balance, currency, status, last_transaction_date) VALUES (?,?,?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, acct, acct_type, bal, curr, status, last_txn))

        # LOANS
        for i in range(8):
            cust = random.choice(customers) + f" L{i}"
            acct = next_acct()
            ltype = random.choice(loan_types)
            orig = round(random.uniform(1000000, 200000000), 2)
            outstanding = round(orig * random.uniform(0.1, 0.9), 2)
            days_ahead = random.choice([-30, -10, -5, -2, 1, 3, 7, 30, 90])
            rep_date = today + timedelta(days=days_ahead)
            status = 'overdue' if days_ahead < 0 else 'active'
            days_ov = abs(days_ahead) if days_ahead < 0 else 0
            c.execute("INSERT INTO loans (rm_id, branch_id, customer_name, account_number, loan_type, outstanding_balance, original_amount, repayment_date, status, days_overdue) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, acct, ltype, outstanding, orig, rep_date, status, days_ov))

        # TRADE SERVICES
        for i in range(6):
            cust = random.choice(customers) + f" T{i}"
            ttype = random.choice(trade_types)
            amount = round(random.uniform(50000, 5000000), 2)
            status = random.choice(['active', 'active', 'inactive', 'dormant', 'completed'])
            exp = today + timedelta(days=random.randint(-60, 180))
            ref = next_ref('TRD')
            c.execute("INSERT INTO trade_services (rm_id, branch_id, customer_name, reference, service_type, amount, currency, status, expiry_date) VALUES (?,?,?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, ref, ttype, amount, 'USD', status, exp))

        # DIGITAL BANKING
        for i in range(10):
            cust = random.choice(customers) + f" D{i}"
            acct = next_acct()
            dtype = random.choice(digital_types)
            status = random.choice(['active', 'active', 'inactive', 'dormant'])
            last_act = today - timedelta(days=random.randint(0, 400))
            tid = f"TID{random.randint(100000,999999)}" if dtype == 'pos' else None
            c.execute("INSERT INTO digital_banking (rm_id, branch_id, customer_name, account_number, product_type, status, terminal_id, last_activity_date) VALUES (?,?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, acct, dtype, status, tid, last_act))

        # CARDS
        for i in range(5):
            cust = random.choice(customers) + f" C{i}"
            acct = next_acct()
            ctype = random.choice(['debit', 'credit'])
            limit = round(random.uniform(100000, 5000000), 2) if ctype == 'credit' else 0
            outstanding = round(limit * random.uniform(0, 1.1), 2) if ctype == 'credit' else 0
            due_days = random.choice([-20, -10, -5, 5, 15, 30])
            due_date = today + timedelta(days=due_days)
            is_overdue = 1 if due_days < 0 and ctype == 'credit' else 0
            days_ov = abs(due_days) if is_overdue else 0
            status = random.choice(['active', 'inactive'])
            c.execute("INSERT INTO cards (rm_id, branch_id, customer_name, account_number, card_type, status, credit_limit, outstanding_balance, payment_due_date, is_overdue, days_overdue) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, acct, ctype, status, limit, outstanding, due_date, is_overdue, days_ov))

        # RETAIL
        for i in range(8):
            cust = random.choice(customers) + f" R{i}"
            acct = next_acct()
            bal = round(random.uniform(5000, 2000000), 2)
            status = random.choice(['active', 'active', 'inactive', 'dormant'])
            last_txn = today - timedelta(days=random.randint(0, 500))
            c.execute("INSERT INTO retail (rm_id, branch_id, customer_name, account_number, balance, status, last_transaction_date) VALUES (?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, acct, bal, status, last_txn))

        # COLLECTIONS
        for i in range(10):
            cust = random.choice(customers) + f" Col{i}"
            acct = next_acct()
            ctype = random.choice(['received', 'paid'])
            amount = round(random.uniform(50000, 10000000), 2)
            col_date = today - timedelta(days=random.randint(0, 90))
            c.execute("INSERT INTO collections (rm_id, branch_id, customer_name, account_number, collection_type, amount, collection_date) VALUES (?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, acct, ctype, amount, col_date))

        # PUBLIC SECTOR (legacy random)
        for i in range(3):
            inst = random.choice(['Federal Ministry of Finance', 'Lagos State Government', 'NNPC', 'CBN', 'NIMASA', 'FAAN']) + f" {i}"
            acct = next_acct()
            bal = round(random.uniform(10000000, 500000000), 2)
            stype = random.choice(['federal', 'state', 'local', 'parastatal'])
            c.execute("INSERT INTO public_sector (rm_id, branch_id, institution_name, account_number, sector_type, balance) VALUES (?,?,?,?,?,?)",
                      (rm_id, branch_id, inst, acct, stype, bal))

        # NXP TRACKER (new)
        for i in range(5):
            cust = random.choice(customers) + f" NXP{i}"
            ref = next_ref('NXP')
            amount = round(random.uniform(50000, 2000000), 2)
            status = random.choice(['pending', 'approved', 'completed'])
            c.execute("INSERT INTO nxp_tracker (rm_id, branch_id, customer_name, reference, amount, currency, status) VALUES (?,?,?,?,?,?,?)",
                      (rm_id, branch_id, cust, ref, amount, 'USD', status))

    # Targets (existing metrics only, no change)
    year = today.year
    month = today.month
    quarter = (month - 1) // 3 + 1
    metrics = ['total_liabilities', 'total_loans', 'digital_onboarding', 'trade_volume', 'collections', 'retail_accounts']
    for rm in rms:
        for metric in metrics:
            for period, pval in [('monthly', month), ('quarterly', quarter), ('yearly', 0)]:
                target = round(random.uniform(50000000, 500000000), 2)
                c.execute("INSERT INTO targets (entity_type, entity_id, metric, period, year, period_value, target_value) VALUES (?,?,?,?,?,?,?)",
                          ('rm', rm['id'], metric, period, year, pval, target))

    conn.commit()
    conn.close()


def seed_public_sector_entities():
    """Insert or update the specific high-value public sector entities."""
    conn = get_db()
    c = conn.cursor()

    # Get a default RM and Branch (first RM and first branch)
    c.execute("SELECT id FROM users WHERE role='rm' LIMIT 1")
    rm = c.fetchone()
    c.execute("SELECT id FROM branches LIMIT 1")
    branch = c.fetchone()

    if not rm or not branch:
        conn.close()
        return  # cannot seed without references

    # Define the list of entities with desired balances (in Naira)
    entities = [
        ("Dangote Industries", "Corporate", 1250000000.00),
        ("Unilever Nigeria", "Corporate", 750000000.00),
        ("Nigerian Breweries", "Corporate", 880000000.00),
        ("Airtel Nigeria", "Corporate", 620000000.00),
        ("MTN Nigeria", "Corporate", 2100000000.00),
        ("GLO Nigeria", "Corporate", 500000000.00),
        ("BUA Cement", "Corporate", 940000000.00),
        ("Ebonyi State IGR", "Government", 125000000.00),
        ("Enugu State IGR", "Government", 142000000.00),
        ("Anambra State IGR", "Government", 168000000.00),
        ("Nigeria Revenue Service", "Government", 3500000000.00),
        ("Nigeria Customs Service", "Government", 2750000000.00),
    ]

    for name, sector_type, balance in entities:
        c.execute("SELECT id, account_number FROM public_sector WHERE institution_name = ?", (name,))
        existing = c.fetchone()
        if existing:
            c.execute("""
                UPDATE public_sector
                SET balance = ?, sector_type = ?, status = 'active', opened_date = date('now')
                WHERE institution_name = ?
            """, (balance, sector_type, name))
        else:
            c.execute("SELECT account_number FROM public_sector WHERE account_number LIKE 'PS%' ORDER BY account_number DESC LIMIT 1")
            last = c.fetchone()
            if last and last['account_number'].startswith('PS'):
                try:
                    num = int(last['account_number'][2:]) + 1
                except:
                    num = 9000001
            else:
                num = 9000001
            acct = f"PS{num}"
            c.execute("""
                INSERT INTO public_sector
                (rm_id, branch_id, institution_name, account_number, sector_type, balance, status, opened_date)
                VALUES (?, ?, ?, ?, ?, ?, 'active', date('now'))
            """, (rm['id'], branch['id'], name, acct, sector_type, balance))

    conn.commit()
    conn.close()