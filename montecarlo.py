import requests, json, random
from datetime import datetime

print("Fetching 5yr BTC data...")
url = "https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000"
data = requests.get(url).json()["Data"]["Data"]
closes = [d["close"] for d in data]
opens  = [d["open"]  for d in data]
vols   = [d["volumefrom"] for d in data]

def ema(prices, period):
    result = [None]*(period-1); k = 2/(period+1)
    e = sum(prices[:period])/period; result.append(e)
    for p in prices[period:]: e = p*k+e*(1-k); result.append(e)
    return result

def rsi(prices, period=14):
    gains,losses = [],[]
    for i in range(1,len(prices)):
        d=prices[i]-prices[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    result=[None]*period; ag=sum(gains[:period])/period; al=sum(losses[:period])/period
    for i in range(period,len(gains)):
        ag=(ag*13+gains[i])/14; al=(al*13+losses[i])/14
        rs=ag/al if al!=0 else 100; result.append(100-100/(1+rs))
    return result

def cum_delta(opens,closes,vols):
    deltas,cum=[],0
    for o,c,v in zip(opens,closes,vols):
        cum+=v if c>=o else -v; deltas.append(cum)
    return deltas

def macd(prices):
    e12=ema(prices,12); e26=ema(prices,26)
    line=[None if e12[i] is None or e26[i] is None else e12[i]-e26[i] for i in range(len(prices))]
    valid_idx=[i for i,v in enumerate(line) if v is not None]
    sig_vals=ema([line[i] for i in valid_idx],9)
    signal=[None]*len(prices)
    for j,i in enumerate(valid_idx):
        if sig_vals[j] is not None: signal[i]=sig_vals[j]
    return line,signal

rsi_vals=rsi(closes); macd_line,macd_sig=macd(closes)
delta=cum_delta(opens,closes,vols)
ema50=ema(closes,50); ema200=ema(closes,200)
n=min(len(closes),len(rsi_vals),len(macd_line),len(macd_sig),len(delta),len(ema50),len(ema200))

# Kumpulkan return % per trade (entry→exit)
trade_returns = []
position = None; prev_m = None
for i in range(200,n):
    r,m,s,price=rsi_vals[i],macd_line[i],macd_sig[i],closes[i]
    if None in [r,m,s,ema50[i],ema200[i]]: continue
    in_up=ema50[i]>ema200[i]; d_bull=delta[i]>delta[i-3]; d_bear=delta[i]<delta[i-3]
    macd_up=prev_m is not None and prev_m<0 and m>0
    macd_dn=prev_m is not None and prev_m>0 and m<0
    prev_m=m
    if position is None and in_up and 45<r<65 and macd_up and d_bull:
        position={"entry":price}
    elif position and ((macd_dn and d_bear) or price<position["entry"]*0.80):
        ret=(price-position["entry"])/position["entry"]
        trade_returns.append(ret)
        position=None
if position:
    ret=(closes[-1]-position["entry"])/position["entry"]
    trade_returns.append(ret); position=None

print(f"Trade returns: {[round(r*100,1) for r in trade_returns]}")
print(f"Total trades: {len(trade_returns)}")

if not trade_returns:
    print("ERROR: tidak ada trade ditemukan!")
    exit()

# Monte Carlo dengan compounding
N_SIM=1000; INITIAL=1000.0; ALLOC=0.4
results=[]
random.seed(42)

for _ in range(N_SIM):
    shuffled=trade_returns.copy(); random.shuffle(shuffled)
    balance=INITIAL; peak=INITIAL; max_dd=0
    for ret in shuffled:
        gain=balance*ALLOC*ret
        balance+=gain
        peak=max(peak,balance)
        dd=(peak-balance)/peak*100
        max_dd=max(max_dd,dd)
    results.append({"ret":(balance-INITIAL)/INITIAL*100,"max_dd":max_dd})

results.sort(key=lambda x:x["ret"])
rets=[r["ret"] for r in results]
dds=[r["max_dd"] for r in results]
profitable=sum(1 for r in rets if r>0)

p5=rets[50]; p25=rets[250]; p50=rets[500]; p75=rets[750]; p95=rets[950]
dd50=sorted(dds)[500]; dd95=sorted(dds)[950]

print(f"\n{'='*50}")
print(f"  MONTE CARLO — Strategy E ({N_SIM} simulasi)")
print(f"{'='*50}")
print(f"  Worst case  (5%) : {p5:+.1f}%")
print(f"  Bad case   (25%) : {p25:+.1f}%")
print(f"  Median     (50%) : {p50:+.1f}%")
print(f"  Good case  (75%) : {p75:+.1f}%")
print(f"  Best case  (95%) : {p95:+.1f}%")
print(f"  {'─'*40}")
print(f"  Prob. Profit     : {profitable/N_SIM*100:.1f}%")
print(f"  Max DD median    : {dd50:.1f}%")
print(f"  Max DD worst 95% : {dd95:.1f}%")
print(f"{'='*50}")
verdict="ROBUST" if profitable/N_SIM>=0.70 and dd95<30 else "PERLU REVIEW"
print(f"\n  Verdict: {verdict}")
json.dump({"timestamp":datetime.now().isoformat(),"trade_returns":trade_returns,
    "p5":round(p5,2),"p50":round(p50,2),"p95":round(p95,2),
    "prob_profit":round(profitable/N_SIM*100,1),
    "max_dd_median":round(dd50,1),"max_dd_worst95":round(dd95,1)},
    open("logs/montecarlo_results.json","w"),indent=2)
print("Saved!")
