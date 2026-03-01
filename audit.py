import os
import re

backend_dir = r"c:\Users\Public\Documents\Inmobiliarias.ai\backend"
routers_dir = os.path.join(backend_dir, "routers")

print("--- AUDIT: SEARCHING FOR ROUTES WITHOUT AUTHENTICATION ---")
auth_pattern = re.compile(r"Depends\(get_current_user_email\)|Depends\(get_current_active_user\)")
route_pattern = re.compile(r"@router\.(get|post|put|delete|patch)\([\'\"]([^\'\"]+)[\'\"]")

for filename in os.listdir(routers_dir):
    if not filename.endswith(".py"): continue
    filepath = os.path.join(routers_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    lines = content.split("\n")
    for i, line in enumerate(lines):
        match = route_pattern.search(line)
        if match:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Check the function definition on the next lines (usually within the next 3 lines)
            func_def = ""
            for j in range(1, 4):
                if i + j < len(lines):
                    func_def += lines[i+j]
                    if "):" in lines[i+j]: break
            
            if not auth_pattern.search(func_def) and "public" not in path and not path.startswith("/webhook"):
                print(f"{filename}:{i+1} - Missing Auth: {method} {path}")

print("\n--- AUDIT: SEARCHING FOR MISSING TENANT_ID IN QUERIES ---")
db_query_pattern = re.compile(r"db\.query\((models\.[a-zA-Z0-9_]+)\)")
for filename in os.listdir(routers_dir):
    if not filename.endswith(".py"): continue
    filepath = os.path.join(routers_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.split("\n")
    for i, line in enumerate(lines):
        match = db_query_pattern.search(line)
        # Exclude models that inherently shouldn't have tenant_id like Users, SystemConfig
        excluded_models = ["models.User", "models.SystemConfig", "models.Tenant", "models.RegistrationToken", "models.AgencyConfig"]
        if match and match.group(1) not in excluded_models:
            if "tenant_id" not in line:
               # check next few lines for multi-line statements
               found_tenant = False
               for j in range(5):
                   if i + j < len(lines) and "tenant_id" in lines[i+j]:
                       found_tenant = True
                       break
               if not found_tenant:
                   print(f"{filename}:{i+1} - Missing Tenant ID filter for {match.group(1)}")
