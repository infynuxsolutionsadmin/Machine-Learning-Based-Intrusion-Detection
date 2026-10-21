import urllib.request, json, time
for n in range(1, 7):
    print(f'Testing Node {n}...')
    data=json.dumps({'scenario': 'blackhole', 'attackerNode': n}).encode('utf-8')
    req=urllib.request.Request('http://127.0.0.1:8000/api/simulation/run', data=data, headers={'Content-Type':'application/json'})
    resp=json.loads(urllib.request.urlopen(req).read().decode())
    for flow in resp['metrics']:
        if flow['flow_id'] == '1':
            print(f"Node {n} Blackhole Flow 1: PDR={flow['pdr_percent']}%")
    time.sleep(1)
