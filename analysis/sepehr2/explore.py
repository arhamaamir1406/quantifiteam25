import pandas as pd, numpy as np, os
D=os.path.join(os.path.dirname(__file__),"..","data")
P=["WHITE_PEARLS","BLACK_PEARLS","GOLDEN_PEARLS","PINK_PEARLS","BLUE_PEARLS"]
for day in (-2,-1,0):
    df=pd.read_csv(f"{D}/prices_day_{day}.csv",sep=";")
    df=df[df["product"].isin(P)]
    mid=df.pivot(index="timestamp",columns="product",values="mid_price")[P]
    spr=(df.assign(s=df.ask_price_1-df.bid_price_1)).pivot(index="timestamp",columns="product",values="s")[P]
    tr=pd.read_csv(f"{D}/trades_day_{day}.csv",sep=";"); tr=tr[tr.symbol.isin(P)]
    print(f"\n===== day {day}  ticks {len(mid)}")
    print("open/close/min/max"); print(pd.DataFrame({"open":mid.iloc[0],"close":mid.iloc[-1],"min":mid.min(),"max":mid.max()}).T.round(0).to_string())
    print("median spread", spr.median().to_dict())
    print("tick-move sd", mid.diff().std().round(2).to_dict())
    print("ac1 of tick moves", {p:round(mid[p].diff().autocorr(),3) for p in P})
    for h in (10,100,500):
        r=mid.diff(h).iloc[::h]
        print(f"ac of {h}-tick moves", {p:round(r[p].autocorr(),2) for p in P})
    s=mid.sum(axis=1); g=s-50000
    print("sum mean/sd/min/max", round(s.mean(),2), round(s.std(),2), s.min(), s.max())
    for h in (1,5,10,50):
        fut=mid.shift(-h)-mid
        print(f"corr(gap, next {h} move)", {p:round(np.corrcoef(g[:-h],fut[p][:-h])[0,1],3) for p in P})
    # trades
    print("trades n/qty", tr.groupby("symbol").quantity.agg(["count","sum"]).to_dict())
    # level book volumes
    bv=df.groupby("product")[["bid_volume_1","ask_volume_1","bid_volume_2","ask_volume_2"]].median()
    print("median L1/L2 vols", bv.to_dict("index"))
