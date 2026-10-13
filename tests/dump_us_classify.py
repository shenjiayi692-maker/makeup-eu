import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src', 'us'))
import classify as C
D = C.Data()
CLAIMS = [[], ['anti-dandruff'], ['reduces underarm wetness'], ['soothes chapped lips'], ['SPF 30 sunscreen'], ['acne treatment'], ['mild cleansing', 'eczema relief']]
out = []
for fid in ['F1a', 'F1b', 'F2', 'F3a', 'F3b', 'F4', 'F5', 'F6', 'F7']:
    for cl in CLAIMS:
        p, ings = C.load_formula(fid)
        out.append({'formula': fid, 'claims': cl, 'result': C.classify(p, ings, D, cl)})
print(json.dumps(out, ensure_ascii=False))
