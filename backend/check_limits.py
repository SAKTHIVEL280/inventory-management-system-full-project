import sys
import os
sys.path.append(os.getcwd())

import app
from app.routers.users import list_users
import inspect

print(f"App location: {app.__file__}")

params = inspect.signature(list_users).parameters
page_size_param = params.get('page_size')
if page_size_param:
    print(f"page_size metadata: {page_size_param.default.json_schema_extra if hasattr(page_size_param.default, 'json_schema_extra') else 'No schema extra'}")
    # Inspecting Query object directly
    q = page_size_param.default
    print(f"Query le: {getattr(q, 'le', 'Not set')}")
else:
    print("page_size param not found")
