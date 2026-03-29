from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:root@localhost:5432/ims_db')
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR'"))
    conn.commit()
    print("Migration successful.")
