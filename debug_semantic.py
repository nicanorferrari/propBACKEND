
import requests

API_URL = "http://127.0.0.1:8000"

def debug_semantic_search():
    try:
        query = "esta buscando una casa en funes"
        print(f"--- DEBUGGING QUERY: '{query}' ---")
        
        # 1. Call the match endpoint
        url = f"{API_URL}/api/ai-matching/match?query={query.replace(' ', '%20')}"
        res = requests.get(url)
        
        if res.status_code == 200:
            data = res.json()
            matches = data.get('matches', [])
            print(f"Found {len(matches)} matches.")
            for i, m in enumerate(matches):
                print(f"\nResult {i+1}:")
                print(f"  Address: {m.get('address')}")
                print(f"  City: {m.get('city')}")
                print(f"  Neighborhood: {m.get('neighborhood')}")
                print(f"  Score: {m.get('score')}")
                print(f"  Description Snippet: {m.get('description')[:100] if m.get('description') else 'None'}")
        else:
            print(f"API Error: {res.status_code} - {res.text}")

    except Exception as e:
        print(f"Script Error: {e}")

if __name__ == "__main__":
    debug_semantic_search()
