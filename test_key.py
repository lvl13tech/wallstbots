import urllib.request, json

base = 'https://wallstbots-backend-868128114349.us-east1.run.app'

req = urllib.request.Request(f'{base}/public/tracker/state?platform=lvl13')
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read())

state = data.get('data', {})
sc = state.get('starting_capital')
funds = state.get('funds', {})
eq_positions = len(funds.get('equalizer', {}).get('value', {}).get('positions', []))
titan_top10 = funds.get('titan', {}).get('top10', [])
last_refresh = state.get('last_refresh')

print(f'pushed_at:        {data.get("pushed_at")}')
print(f'last_refresh:     {last_refresh}')
print(f'starting_capital: ${sc:,.0f}' if sc else f'starting_capital: {sc} (dummy data still in DB — run the Action)')
print(f'EQUALIZER stocks: {eq_positions}')
print(f'TITAN top10:      {titan_top10}')
