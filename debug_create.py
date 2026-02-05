import os
import requests
import json

EVO_URL = "https://propcrm-evolution-api.rjcuax.easypanel.host"
EVO_KEY = "429683C4C977415CAAFCCE10F7D57E11"

instance_name = "urbano_crm_user_11"
headers = {"apikey": EVO_KEY, "Content-Type": "application/json"}
create_payload = {
    "instanceName": instance_name,
    "token": "bot_tk_11",
    "qrcode": True,
    "integration": "WHATSAPP-BAILEYS"
}
res = requests.post(f"{EVO_URL}/instance/create", headers=headers, json=create_payload)
print(f"Status: {res.status_code}")
print(res.text)
