
import os
import sys
from sqlalchemy import create_engine, text
import bcrypt

def get_password_hash(password):
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

DATABASE_URL = "postgresql://postgres:c1dd6c9314aa474b2ca4@179.43.119.138:54322/propcrm"

engine = create_engine(DATABASE_URL)

def run():
    try:
        with engine.connect() as conn:
            # 1. Create Tenant
            tenant_name = "Inmobiliaria Siglo XXI"
            domain = "sigloxxi.propcrm.com"
            
            res = conn.execute(text("SELECT id FROM tenants WHERE name = :name"), {"name": tenant_name}).fetchone()
            if res:
                tenant_id = res[0]
                print(f"Tenant '{tenant_name}' already exists with ID {tenant_id}")
            else:
                res = conn.execute(
                    text("INSERT INTO tenants (name, domain) VALUES (:name, :domain) RETURNING id"),
                    {"name": tenant_name, "domain": domain}
                )
                tenant_id = res.fetchone()[0]
                conn.commit()
                # Fresh connection/commit to ensure tenant exists for next queries
                print(f"Created Tenant '{tenant_name}' with ID {tenant_id}")

            # 2. Create Users
            users_to_create = [
                {"email": "admin@sigloxxi.com", "password": "adminSiglo2024", "role": "BROKER_ADMIN", "first_name": "Admin", "last_name": "Siglo XXI"},
                {"email": "broker@sigloxxi.com", "password": "brokerSiglo2024", "role": "BROKER_ADMIN", "first_name": "Broker", "last_name": "Siglo XXI"},
                {"email": "agente1@sigloxxi.com", "password": "agenteSiglo2024", "role": "agent", "first_name": "Agente", "last_name": "Uno"}
            ]

            for u in users_to_create:
                res = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": u["email"]}).fetchone()
                if res:
                    print(f"User {u['email']} already exists")
                    continue
                
                hashed = get_password_hash(u["password"])
                conn.execute(
                    text("INSERT INTO users (email, hashed_password, role, tenant_id, first_name, last_name, name, is_active) VALUES (:email, :hashed, :role, :tenant_id, :first_name, :last_name, :name, true)"),
                    {
                        "email": u["email"],
                        "hashed": hashed,
                        "role": u["role"],
                        "tenant_id": tenant_id,
                        "first_name": u["first_name"],
                        "last_name": u["last_name"],
                        "name": f"{u['first_name']} {u['last_name']}"
                    }
                )
                print(f"Created User {u['email']} with role {u['role']}")
            
            conn.commit()
            print("Successfully created all users for Inmobiliaria Siglo XXI.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run()
