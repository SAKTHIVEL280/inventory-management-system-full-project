import json
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:root@localhost:5432/ims_db')
with engine.connect() as conn:
    res = conn.execute(text("SELECT COUNT(*) FROM sales_orders")).scalar()
    print(f"Total Sales Orders: {res}")
    
    res2 = conn.execute(text("SELECT status, COUNT(*) FROM sales_orders GROUP BY status")).fetchall()
    print(f"Statuses SOs: {res2}")
    
    res3 = conn.execute(text("SELECT COUNT(*) FROM purchase_orders")).scalar()
    print(f"Total Purchase Orders: {res3}")
