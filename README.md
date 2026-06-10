# Performance-Portfolio-Management
# PMPMS – Portfolio Monitoring & Performance Management System

A comprehensive web-based dashboard for Nigerian banks to monitor liability portfolios, credit facilities, trade services, digital banking adoption, collections, and performance targets through a centralized analytics platform.

---

## 🏦 Overview

PMPMS aggregates data from multiple banking systems into a unified real-time monitoring platform. It enables bank executives and operational staff to track portfolio performance, monitor targets, and make informed business decisions.

### Core Capabilities

* Executive dashboards with KPIs and alerts
* Performance tracking against targets
* Data filtering and export (Excel/CSV)
* Automated liability and income projections
* Hierarchical drill-down from Zones → Branches → Relationship Managers (RMs)
* Real-time portfolio analytics

### Supported Banking Modules

* CABAL (Liability Accounts)
* Loans
* Trade Services
* Digital Banking
* Cards
* Retail Banking
* Collections
* Public Sector Accounts
* NXP Tracker

### Localization Features

* Nigerian Naira (₦) currency formatting
* FX conversion support (USD, GBP, EUR → NGN)
* Nigerian date formatting standards

---

## ✨ Key Features

### 📊 Dashboard

The dashboard provides:

* Real-time KPI cards
* Portfolio composition visualization
* Account status analytics
* Automated alerts and notifications

#### KPI Metrics

* Total liabilities
* Loan portfolio value
* Overdue facilities
* Collections performance
* Digital banking adoption
* Active customer accounts

#### Alerts

* Overdue loans
* Facilities nearing due dates
* Dormant trade accounts
* Overdue credit card accounts

---

### 📋 Banking Modules

| Module          | Description                                        |
| --------------- | -------------------------------------------------- |
| CABAL           | Current, Savings, Fixed Deposit, and FX accounts   |
| Loans           | Term loans, overdrafts, bonds, and guarantees      |
| Trade Services  | Form M, Form A, Letters of Credit, FX transactions |
| Digital Banking | Mobile banking, POS, Internet banking, USSD        |
| Cards           | Debit and credit card management                   |
| Retail          | Retail savings and current accounts                |
| Collections     | Incoming and outgoing transactions                 |
| Public Sector   | Government and corporate accounts                  |

---

### 🎯 Targets & KPIs

The system supports monthly, quarterly, and yearly targets for:

* Total liabilities
* Loan portfolio growth
* Digital onboarding
* Trade service volumes
* Collections performance
* Retail account growth
* Month-to-date account opening
* Active NXP trackers

#### Tracking Features

* Progress indicators
* Actual vs Target comparisons
* Performance monitoring dashboards

---

### 📈 Financial Projections

#### Available Projections

* 6-month product-level forecasts
* Liability growth projections
* Income projections
* Consolidated performance forecasting

#### Product Categories

* DDA Accounts
* Savings Accounts
* Fixed Deposits
* Foreign Currency Accounts

#### Insights

* Growth trend analysis
* Strategic recommendations
* Income forecasting

---

### 🗂️ Hierarchical Drill-Down

#### Managing Director

* View all zones
* View all branches
* View all RMs

#### Zonal Head

* View assigned zone
* View branches within zone
* View associated RMs

#### Branch Head

* View branch performance
* View all RMs within branch

#### Relationship Manager

* View personal portfolio
* Access customer-level details
* Export portfolio reports

---

## 🔐 Role-Based Access Control

| Role                      | Access Scope                 |
| ------------------------- | ---------------------------- |
| Managing Director (MD)    | Full access across all zones |
| Zonal Head                | Assigned zone and branches   |
| Branch Head               | Assigned branch and RMs      |
| Relationship Manager (RM) | Own customer portfolio       |

---

## 📤 Data Export

Supported export formats:

* Excel (.xlsx)
* CSV

Features include:

* Professional Excel formatting
* Module-specific exports
* RM portfolio exports

---

## 🛠️ Technology Stack

| Layer         | Technology                |
| ------------- | ------------------------- |
| Backend       | Python 3.10+, Flask       |
| Database      | SQLite                    |
| Frontend      | HTML5, CSS3, JavaScript   |
| Charts        | Chart.js 4.4              |
| Export Engine | openpyxl                  |
| Security      | Werkzeug Password Hashing |

---

## 📦 Installation

### Prerequisites

* Python 3.10+
* pip

### Clone Repository

```bash
git clone https://github.com/your-org/pmpms.git
cd pmpms
```

### Create Virtual Environment

**Linux/macOS**

```bash
python -m venv venv
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install flask werkzeug openpyxl
```

### Run Application

```bash
python app.py
```

### Access Application

Open:

```text
http://localhost:5000
```

The database is automatically created and populated with sample data during first startup.



## ⚙️ Configuration

### Security

Update the Flask secret key before deployment:

```python
app.secret_key = "your-secure-secret-key"
```

### Database

Modify the database path in:

```python
database.py
```

### FX Conversion Rates

| Currency | NGN Rate |
| -------- | -------- |
| USD      | 1500     |
| GBP      | 2000     |
| EUR      | 1800     |

### Projection Growth Rates

Adjust projection assumptions in:

```python
api_projections_detailed
```

---

## 📁 Project Structure

```text
pmpms/
├── app.py
├── database.py
├── templates/
│   └── dashboard.html
├── instance/
│   └── pmpms.db
└── README.md
```

---

## 🗄️ Database Schema

### Core Tables

* users
* zones
* branches
* cabal
* loans
* trade_services
* digital_banking
* cards
* retail
* collections
* public_sector
* nxp_tracker
* targets

### Targets Table

Stores:

* Entity type
* Metric
* Reporting period
* Target value

---

## 📡 API Endpoints

All endpoints require authentication and are prefixed with:

```text
/api/
```

| Endpoint                      | Method    | Description              |
| ----------------------------- | --------- | ------------------------ |
| /dashboard/summary            | GET       | KPI summary and alerts   |
| /cabal                        | GET       | Liability accounts       |
| /loans                        | GET       | Loan portfolio           |
| /trade                        | GET       | Trade services           |
| /digital                      | GET       | Digital banking          |
| /cards                        | GET       | Card services            |
| /retail                       | GET       | Retail accounts          |
| /collections                  | GET       | Collections              |
| /public_sector                | GET       | Public sector accounts   |
| /projections                  | GET       | Basic projections        |
| /projections/detailed         | GET       | Advanced projections     |
| /targets                      | GET, POST | Manage targets           |
| /hierarchy                    | GET       | Organizational hierarchy |
| /hierarchy/zone/<id>/branches | GET       | Zone branches            |
| /hierarchy/branch/<id>/rms    | GET       | Branch RMs               |
| /rm_detail/<id>               | GET       | RM portfolio details     |
| /export/<module>              | GET       | Export module data       |

---

## 🧪 Testing & Sample Data

### Organizational Structure

* 3 Zones
* 7 Branches

### Users

* 1 Managing Director
* 3 Zonal Heads
* 3 Branch Heads
* 6 Relationship Managers

### Banking Data

* CABAL accounts
* Loan facilities
* Trade transactions
* Digital banking records
* Card accounts
* Retail accounts
* Collections data
* Public sector portfolios
* NXP trackers
* Performance targets

### Database Reset

Delete:

```text
instance/pmpms.db
```

Then restart the application.

---

## 🚀 Production Deployment

### Recommended Actions

1. Replace the default secret key.
2. Disable Flask debug mode.
3. Deploy behind Nginx or Apache.
4. Enable HTTPS.
5. Use PostgreSQL or MySQL for production workloads.
6. Run with a production WSGI server.

### Gunicorn Example

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

## 🤝 Contributing

This is an internal banking application.

For support, enhancements, or issue reporting, contact the IT or PMO team.

---

## 📄 License

**Proprietary Software**

For internal organizational use only. Distribution outside the organization is prohibited.

---

## 🙏 Acknowledgements

* Built using Flask and Chart.js
* Designed for banking performance analytics
* Validated by Relationship Managers and Branch Heads
