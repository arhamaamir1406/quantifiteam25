import pandas as pd, numpy as np, os
D=os.path.join(os.path.dirname(__file__),"..","data")
P=["WHITE_PEARLS","BLACK_PEARLS","GOLDEN_PEARLS","PINK_PEARLS","BLUE_PEARLS"]
for day in (-2,-1,0):
    df=pd.read_csv(f"{D}/prices_day_{day}.csv",sep=";"); df=df[df["product"].isin(P)]
    mid=df.pivot(index="timestamp",columns="product",values="mid_price")[P]
    bid=df.pivot(index="timestamp",columns="product",values="bid_price_1")[P]
    ask=df.pivot(index="timestamp",columns="product",values="ask_price_1")[P]
    others=mid.drop(columns="PINK_PEARLS").sum(axis=1)
    fair=50000-others; dev=fair-mid.PINK_PEARLS
    print(f"\n===== day {day}")
    print("PINK dev (fair-mid) sd %.2f  |dev|>2: %.1f%%  >4: %.1f%%  >6: %.1f%%"%(dev.std(),100*(dev.abs()>2).mean(),100*(dev.abs()>4).mean(),100*(dev.abs()>6).mean()))
    for h in (1,2,5,10,20,50,100):
        fut=mid.PINK_PEARLS.shift(-h)-mid.PINK_PEARLS
        b=np.polyfit(dev[:-h],fut[:-h],1)[0]
        print(f"  PINK next-{h} move = {b:.2f} x dev")
    # how far is fair from PINK's quotes: chance of profitable take
    print("  ask <= fair-1: %.1f%%  bid >= fair+1: %.1f%%"%(100*(ask.PINK_PEARLS<=fair-1).mean(),100*(bid.PINK_PEARLS>=fair+1).mean()))
    # dev autocorr
    print("  dev autocorr lag1/5/20:",[round(dev.autocorr(l),2) for l in (1,5,20)])
    # BLUE momentum small horizons
    for p in ["BLUE_PEARLS","WHITE_PEARLS","BLACK_PEARLS"]:
        print(" ",p,"ac k-tick moves", {k:round(mid[p].diff(k).iloc[::k].autocorr(),2) for k in (2,3,5,10,20,50,200)})
    # GOLDEN levels
    g=mid.GOLDEN_PEARLS
    vc=g.round().value_counts().head(6)
    print("  GOLDEN top levels", vc.to_dict())
    ch=g.round(-1); idx=np.where(ch.diff().abs()>0)[0]
    # trades
    tr=pd.read_csv(f"{D}/trades_day_{day}.csv",sep=";"); tr=tr[tr.symbol.isin(P)]
    j=tr.merge(df[["timestamp","product","bid_price_1","ask_price_1","mid_price"]],left_on=["timestamp","symbol"],right_on=["timestamp","product"])
    j["at"]=np.where(j.price>=j.ask_price_1,"ask",np.where(j.price<=j.bid_price_1,"bid","inside"))
    print("  trade location", j.groupby(["symbol","at"]).size().unstack(fill_value=0).to_dict("index"))
