"""Verify that required columns exist in suppliers table."""
from sqlalchemy import create_engine, text
import os

database_url = os.getenv("DATABASE_URL", "postgresql://ims_user:root@localhost:5432/ims_db")
engine = create_engine(database_url)

required_columns = [
    'gstin_status',
    'business_type',
    'billing_country',
    'company_director_name',
    'company_director_contact'
]

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'suppliers' AND column_name = ANY(:cols) "
        "ORDER BY column_name"
    ), {"cols": required_columns})
    
    existing_columns = [row[0] for row in result]
    
print(f"Required columns found: {len(existing_columns)}/{len(required_columns)}")
for col in required_columns:
    status = "✅" if col in existing_columns else "❌"
    print(f"  {status} {col}")

if len(existing_columns) == len(required_columns):
    print("\n✅ All required columns exist in suppliers table!")
else:
    missing = set(required_columns) - set(existing_columns)
    print(f"\n❌ Missing columns: {missing}")
