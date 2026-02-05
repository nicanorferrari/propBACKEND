import requests
import json

EVO_URL = "https://propcrm-evolution-api.rjcuax.easypanel.host"
EVO_KEY = "429683C4C977415CAAFCCE10F7D57E11"
instance_name = "urbano_crm_user_11"
headers = {"apikey": EVO_KEY}

res = requests.get(f"{EVO_URL}/instance/connectionState/{instance_name}", headers=headers)
print(json.dumps(res.json(), indent=2))
