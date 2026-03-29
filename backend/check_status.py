from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:root@localhost:5432/ims_db')
with engine.connect() as conn:
    print("Sales Orders:")
    res = conn.execute(text("SELECT status, COUNT(*) FROM sales_orders WHERE is_deleted=FALSE GROUP BY status"))
    for r in res:
        print(r)
    
    print("Purchase Orders:")
    res = conn.execute(text("SELECT status, COUNT(*) FROM purchase_orders WHERE is_deleted=FALSE GROUP BY status"))
    for r in res:
        print(r)
