import requests
api_key = "c311a1a3-2111-40d7-8e18-9406f9da063a"
# Endpoint per il database delle flotte, non per il traffico live
url = "https://airlabs.co/api/v9/fleets"
params = {
    "api_key": api_key,
    "hex": "4ca63b"  # Ryanair
}
r = requests.get(url, params=params)
print("Status:", r.status_code)
print("Risposta:", r.text)