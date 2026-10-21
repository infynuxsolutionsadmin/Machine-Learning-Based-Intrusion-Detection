import urllib.request
import json
res = urllib.request.urlopen("http://127.0.0.1:8000/api/trust/dynamic").read().decode("utf-8")
data = json.loads(res)
preds = data.get("trust_scores", data.get("predictions", []))
if not preds:
    print("Could not find predictions key in", list(data.keys()))
else:
    min_scores = {}
    for p in preds:
        n = p['node']
        s = p['predicted_trust_score']
        if n not in min_scores or s < min_scores[n]:
            min_scores[n] = s
    for k, v in sorted(min_scores.items()):
        print(f"Node {k}: {v}")
