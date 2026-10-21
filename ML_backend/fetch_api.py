import urllib.request, json
res = urllib.request.urlopen("http://127.0.0.1:8000/api/trust/dynamic").read().decode("utf-8")
with open("raw_api.json", "w") as f:
    f.write(res)
