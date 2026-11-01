import pandas as pd, numpy as np, os
D=os.path.join(os.path.dirname(__file__),"..","data")
for day in (-2,-1,0):
    df=pd.read_csv(f"{D}/prices_day_{day}.csv",sep=";")
    for p in ("WHITE_PEARLS","BLACK_PEARLS","PINK_PEARLS"):
        m=df[df["product"]==p].mid_price.reset_index(drop=True)
        past=m.diff(5); fut=m.shift(-10)-m; sd5=past.std()
        big_dn=fut[past<-2*sd5].mean(); big_up=fut[past>2*sd5].mean()
        d30=m.diff(30); 
        print(f"day {day} {p:13s} 5-tick sd {sd5:5.2f}  after big drop next10 {big_dn:+.2f} (n={(past<-2*sd5).sum()})  after big rise {big_up:+.2f} (n={(past>2*sd5).sum()})  30-tick moves beyond 4sd: {(d30.abs()>4*d30.std()).sum()}  max|30-tick| {d30.abs().max():.0f} (sd {d30.std():.1f})")
    g=df[df["product"]=="GOLDEN_PEARLS"].mid_price.reset_index(drop=True)
    lv=g.where((g-g.rolling(20).median()).abs()<1.5)
    ch=np.where(g.diff(5).abs()>5)[0]
    if len(ch):
        groups=np.split(ch, np.where(np.diff(ch)>10)[0]+1)
        print(f"day {day} GOLDEN slides:", [(int(x[0]), float(g[max(0,x[0]-5)]), float(g[min(len(g)-1,x[-1])]), int(x[-1]-x[0])) for x in groups])
    # GOLDEN within-plateau book
    gb=df[df["product"]=="GOLDEN_PEARLS"]
    print(f"day {day} GOLDEN bid/ask most common:", (gb.bid_price_1.astype(int).astype(str)+"/"+gb.ask_price_1.astype(int).astype(str)).value_counts().head(6).to_dict())
