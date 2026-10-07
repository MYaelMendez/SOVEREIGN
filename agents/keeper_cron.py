#!/usr/bin/env python3
"""Cloud keeper cron - audit droplet state, write ledger, publish receipts."""
import json, os, time, urllib.request, hashlib, hmac

STORE = '/opt/aevps/store.json'
SIGN_KEY = os.environ.get('VPS_SIGN_KEY', 'droplet-keeper-key')

def load_store():
    with open(STORE, 'r') as f:
        return json.load(f)

def save_store(store):
    with open(STORE, 'w') as f:
        json.dump(store, f, indent=2)

def sign(value):
    return hmac.new(SIGN_KEY.encode(), json.dumps(value, separators=(',',':')).encode(), 'sha256').hexdigest()[:16]

def make_record(nsid, value):
    body = json.dumps(value, separators=(',',':')).encode()
    sig = sign(value)
    return {'nsid': nsid, 'value': value, 'sig': sig, 'ts': time.time()}

def audit(store):
    events = store.get('ae.core#ledgerEvent', [])
    posts = store.get('ae.social#post', [])
    
    # 1. Droplet uptime check
    try:
        r = urllib.request.urlopen('http://127.0.0.1:3000/', timeout=3)
        vps_up = r.read().decode()
    except:
        vps_up = 'down'
    
    event = make_record('ae.core#ledgerEvent', {
        'kind': 'keeper-audit',
        'vps': vps_up,
        'ledger_entries': len(events),
        'social_posts': len(posts),
        'timestamp': time.time()
    })
    events.append(event)
    
    # 2. Post to social if vps up
    if vps_up != 'down':
        post = make_record('ae.social#post', {
            'text': f'keeper audit: vps up, {len(events)} ledger entries',
            'kind': 'fact',
            'evidence': 'keeper cron audit',
            'agent': 'keeper',
            'principal': 'did:web:myaelmendez.github.io',
            'tags': ['keeper', 'audit', 'droplet'],
            'measured': True,
            'createdAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        })
        posts.append(post)
    
    store['ae.core#ledgerEvent'] = events
    store['ae.social#post'] = posts
    save_store(store)
    
    return {'ledger': len(events), 'posts': len(posts), 'vps': vps_up}

if __name__ == '__main__':
    store = load_store()
    result = audit(store)
    print(json.dumps(result))
