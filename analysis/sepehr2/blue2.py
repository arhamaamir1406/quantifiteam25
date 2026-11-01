import pandas as pd, numpy as np, os
D=os.path.join(os.path.dirname(__file__),"..","data")
for day in (-2,-1,0):
    df=pd.read_csv(f"{D}/prices_day_{day}.csv",sep=";"); m=df[df["product"]=="BLUE_PEARLS"].set_index("timestamp").mid_price.reset_index(drop=True)
    past=m.diff(5); fut=m.shift(-10)-m
    print(f"\n== day {day}: past5>8 -> next10 mean %.2f n=%d ; past5<-8 -> %.2f n=%d" % (fut[past>8].mean(), (past>8).sum(), fut[past<-8].mean(), (past<-8).sum()))
    # find drop events: 30-tick move < -25
    d30=m.diff(30)
    ev=[]; i=0
    while i<len(m):
        if d30.iloc[i] is not None and d30.iloc[i] < -25:
            s=i-30; e=i
            while e+1<len(m) and m.iloc[e+1] < m.iloc[e]+1: e+=1
            ev.append((s, round(m.iloc[s]), round(m.iloc[min(e,len(m)-1)]), e-s)); i=e+50
        else: i+=1
    print(" drops (start tick, from, to, ticks):", ev[:20], "count", len(ev))
    up=[]; i=0
    while i<len(m):
        if d30.iloc[i] > 25:
            up.append((i-30, round(m.iloc[i-30]), round(m.iloc[i]))); i+=50
        else: i+=1
    print(" rises >25 in 30 ticks:", up[:10], "count", len(up))
    # largest 1-tick moves
    print(" biggest tick moves:", m.diff().abs().sort_values().tail(5).round(1).to_dict())
