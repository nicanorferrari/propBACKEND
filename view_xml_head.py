import requests

url = "https://feeds.adinco.net/18618/ar_adinco.xml"
response = requests.get(url)
content = response.text

# Split by lines and take the first 50
lines = content.split('\n')
for line in lines[:50]:
    print(line)
