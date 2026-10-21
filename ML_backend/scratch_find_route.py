import urllib.request, json, time

for i in range(10):
    data=json.dumps({'nNodes': 8, 'maliciousNodes': ['3'], 'sourceNode': 0, 'destinationNode': 6, 'attackEnabled': True}).encode('utf-8')
    req=urllib.request.Request('http://127.0.0.1:8000/api/simulation/run', data=data, headers={'Content-Type': 'application/json'})
    try:
        resp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
        print("Run", i, "status:", resp['status'])
        
        req_rt = urllib.request.Request('http://127.0.0.1:8000/api/routing/path')
        rt_resp = json.loads(urllib.request.urlopen(req_rt).read().decode('utf-8'))
        if rt_resp.get("route_available"):
            print("ROUTE FOUND!", rt_resp['hops'])
            break
        else:
            print("No route:", rt_resp.get("note"))
    except Exception as e:
        print("Error:", e)
