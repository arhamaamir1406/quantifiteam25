import pandas as pd, numpy as np, os
D=os.path.join(os.path.dirname(__file__),"..","data")
for day in (-2,-1,0):
    df=pd.read_csv(f"{D}/prices_day_{day}.csv",sep=";"); b=df[df["product"]=="BLUE_PEARLS"].set_index("timestamp")
    m=b.mid_price.values; spr=(b.ask_price_1-b.bid_price_1).values
    print(f"\n== day {day}: spread dist", pd.Series(spr).value_counts().head(5).to_dict())
    d=np.diff(m); print(" tick move dist", pd.Series(d).value_counts().head(9).to_dict())
    # runs: how long do same-sign moves persist (ignoring zeros)
    nz=np.sign(d[d!=0]); runs=[]; c=1
    for i in range(1,len(nz)):
        if nz[i]==nz[i-1]: c+=1
        else: runs.append(c); c=1
    print(" run length of same-direction nonzero moves: mean %.2f  (random walk ~2.0)  P(run>=4) %.3f"%(np.mean(runs), np.mean(np.array(runs)>=4)))
    past=pd.Series(m).diff(5); fut=pd.Series(m).shift(-10)-pd.Series(m)
    q=pd.cut(past,[-99,-8,-5,-3,-1,1,3,5,8,99])
    print(" next-10 move by past-5 move bucket:", fut.groupby(q,observed=True).agg(["mean","count"]).round(2).T.to_dict())
