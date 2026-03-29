import json
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:root@localhost:5432/ims_db')
with engine.connect() as conn:
    print("ALL SALES ORDERS:")
    res = conn.execute(text("SELECT id, so_number, status, is_deleted FROM sales_orders"))
    for r in res:
        print(r)
    
    print("ALL QUOTATIONS:")
    res = conn.execute(text("SELECT id, status, is_deleted FROM quotations"))
    for r in res:
        print(r)
