import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.database import account_engine, system_engine

def fix_schema():
    for name, eng in [('account', account_engine), ('system', system_engine)]:
        if eng is None:
            continue
        print(f"Checking {name} engine...")
        try:
            with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name = 'catalog_v2_connections'")).fetchall()
                if not tables:
                    print(f"  No catalog_v2_connections table in {name} engine.")
                    continue
                print(f"  Found catalog_v2_connections in {name} engine. Applying schema updates...")
                
                # 1. Drop NOT NULL on schema_id, catalog_name, schema_name
                for col in ['schema_id', 'catalog_name', 'schema_name']:
                    try:
                        conn.execute(text(f"ALTER TABLE catalog_v2_connections ALTER COLUMN {col} DROP NOT NULL;"))
                        print(f"  [OK] Dropped NOT NULL on column '{col}'")
                    except Exception as e:
                        print(f"  [NOTE] {col}: {e}")

                # 2. Check if full_name is generated always
                is_gen = conn.execute(text("""
                    SELECT a.attgenerated 
                    FROM pg_attribute a 
                    JOIN pg_class c ON a.attrelid = c.oid 
                    WHERE c.relname = 'catalog_v2_connections' AND a.attname = 'full_name'
                """)).scalar()
                print(f"  Current attgenerated on 'full_name': {repr(is_gen)}")
                
                if is_gen and str(is_gen) != '':
                    print("  Converting 'full_name' from GENERATED ALWAYS to standard column...")
                    conn.execute(text("ALTER TABLE catalog_v2_connections DROP COLUMN full_name;"))
                    conn.execute(text("ALTER TABLE catalog_v2_connections ADD COLUMN full_name VARCHAR(765);"))
                    conn.execute(text("UPDATE catalog_v2_connections SET full_name = COALESCE(catalog_name || '.' || schema_name || '.' || name, name);"))
                    conn.execute(text("ALTER TABLE catalog_v2_connections ALTER COLUMN full_name SET NOT NULL;"))
                    print("  [OK] Successfully converted 'full_name' to standard column!")
                else:
                    print("  [OK] 'full_name' is already a standard column.")
        except Exception as exc:
            print(f"  Error on {name} engine: {exc}")

if __name__ == "__main__":
    fix_schema()
