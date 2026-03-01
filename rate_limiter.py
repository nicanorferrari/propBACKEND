from slowapi import Limiter
from slowapi.util import get_remote_address

# This uses the IP address of the requester. When behind a proxy (like Nginx),
# ensure that standard headers (X-Forwarded-For) are handled properly.
# FastAPI and uvicorn ProxyHeadersMiddleware handle this if configured.
limiter = Limiter(key_func=get_remote_address)
