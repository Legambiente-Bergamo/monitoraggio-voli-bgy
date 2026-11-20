import requests
api_key = "c311a1a3-2111-40d7-8e18-9406f9da063a"
# Uso un aereo Ryanair che vola spesso (4ca63b) e un ICAO di un volo appena tracciato
params = {
    "api_key": api_key,
    "hex": "4ca63b"
}
r = requests.get("https://airlabs.co/api/v9/aircraft", params=params)
print("Status:", r.status_code)
print("Risposta:", r.text)