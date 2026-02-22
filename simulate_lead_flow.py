import requests
import time
import sys
import os

# Configuration
BASE_URL = "http://localhost:8000/api/whatsapp/webhook"
# Unique phone for this simulation to simulate a fresh lead
PHONE = "5493415556677" 
JID = f"{PHONE}@s.whatsapp.net"
INSTANCE = "urbano_crm_user_1" # Assuming user 1 exists, standard instance name

def send_msg(text):
    print(f"\n[SIMULATION] User: '{text}'")
    payload = {
        "event": "messages.upsert",
        "instance": INSTANCE,
        "data": {
            "key": {
                "remoteJid": JID,
                "fromMe": False,
                "id": f"MSG_TEST_{time.time()}"
            },
            "pushName": "Simulated Lead",
            "message": {
                "conversation": text
            }
        }
    }
    
    try:
        r = requests.post(BASE_URL, json=payload)
        if r.status_code == 200:
            print(f"[API] Response: {r.text}")
            resp_json = r.json()
            if resp_json.get("status") == "error":
                print(f"!!! BACKEND ERROR: {resp_json.get('detail')} !!!")
        else:
            print(f"[API] Error {r.status_code}: {r.text}")
    except requests.exceptions.ConnectionError:
        print("[API] Connection Error: Is the backend running on localhost:8000?")
        sys.exit(1)
    except Exception as e:
        print(f"[API] Unexpected Error: {e}")

def main():
    print("--- STARTING LEAD GENERATION SIMULATION ---")
    print(f"Target: {BASE_URL}")
    print(f"Phone: {PHONE}")

    # 1. Initial Inquiry
    send_msg("Hola, busco departamento de 2 dormitorios en el centro de Rosario")
    print("[SIMULATION] Waiting for bot response (10s)...")
    time.sleep(10)

    # 2. Selecting Property
    send_msg("Me interesa el de San Lorenzo al 1000")
    print("[SIMULATION] Waiting for bot response (10s)...")
    time.sleep(10)

    # 3. Closing / Call to Action
    send_msg("Genial, quiero coordinar una visita para verlo.")
    print("[SIMULATION] Waiting for bot response (10s)...")
    time.sleep(10)

    print("\n--- SIMULATION COMPLETE ---")
    print("Check backend logs for bot responses and logic execution.")

if __name__ == "__main__":
    main()
