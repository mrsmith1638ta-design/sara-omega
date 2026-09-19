import argparse, json
from sara_unified.app import SARAUnified

def main(argv=None):
    p=argparse.ArgumentParser(prog="sara-unified"); p.add_argument("command",choices=["health","ready"]); p.add_argument("--audit",default="./sara-audit.jsonl"); args=p.parse_args(argv)
    app=SARAUnified.local(args.audit)
    if args.command=="health": print(json.dumps({"alive":True,"audit_chain_valid":app.audit.verify()}))
    else: print(json.dumps(app.health.status()))
    return 0
