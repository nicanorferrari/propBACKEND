import os
import requests
import json

EVO_URL = "https://propcrm-evolution-api.rjcuax.easypanel.host"
EVO_KEY = "429683C4C977415CAAFCCE10F7D57E11"
instance_name = "urbano_crm_user_11"
headers = {"apikey": EVO_KEY, "Content-Type": "application/json"}

# Get QR
res = requests.get(f"{EVO_URL}/instance/connect/{instance_name}", headers=headers)
data = res.json()
print("Keys:", list(data.keys()))
if "qrcode" in data:
    print("qrcode keys:", list(data["qrcode"].keys()))
    if "base64" in data["qrcode"]:
        print("QR size:", len(data["qrcode"]["base64"]))
elif "base64" in data:
    print("Base64 size:", len(data["base64"]))
else:
    print("Full structure:", data)
