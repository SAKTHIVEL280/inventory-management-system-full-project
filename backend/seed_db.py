import os
os.chdir('.')
from app.database import engine, Base
from sqlalchemy.orm import sessionmaker
from app.models.user import User

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("✓ Tables created")

print("Seeding admin user...")
Session = sessionmaker(bind=engine)
db = Session()

existing = db.query(User).filter(User.email == "admin@company.com").first()
if not existing:
    # Manually hash password using bcrypt directly (avoiding passlib issue)
    import bcrypt
    password = "Admin@123"
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    admin = User(
        full_name="System Administrator",
        email="admin@company.com",
        hashed_password=hashed,
        role="admin",
        is_active=True,
        force_password_change=True,
    )
    db.add(admin)
    db.commit()
    print("✓ Admin created: admin@company.com / Admin@123")
else:
    print("✓ Admin already exists")

db.close()
print("\n✓ Database ready!")
