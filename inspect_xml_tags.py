import requests
import xml.etree.ElementTree as ET

url = "https://feeds.adinco.net/18618/ar_adinco.xml"
try:
    response = requests.get(url)
    response.encoding = 'utf-8' # Ensure utf-8
    content = response.text
    
    # Parse XML
    root = ET.fromstring(content)
    
    # Get first ad
    first_ad = root.find('ad')
    if first_ad is not None:
        print("Tags inside <ad>:")
        for child in first_ad:
            print(f"  {child.tag}: {child.text}")
            
except Exception as e:
    print(e)
