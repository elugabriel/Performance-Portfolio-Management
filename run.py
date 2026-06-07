"""
PMPMS - Performance Monitoring & Portfolio Management System
Nigerian Financial Services

Run: python run.py
Then open: http://localhost:5000

Default login credentials:
  MD:          md_admin / password
  Zonal Head:  zonal_lagos / password
  Branch Head: bh_vi / password
  RM:          rm_ade / password
"""
from database import init_db
from app import app

if __name__ == '__main__':
    print("Initializing PMPMS database...")
    init_db()
    print("Starting PMPMS server at http://localhost:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)
