import pandas as pd, numpy as np, sys, os
log=pd.read_csv(sys.argv[1],sep=";")
D=os.path.join(os.path.dirname(__file__),"..","data")
for (day,p),g in log.groupby(["day","product"]):
    pr=pd.read_csv(f"{D}/prices_day_{day}.csv",sep=";"); m=pr[pr["product"]==p].set_index("timestamp").mid_price
    g=g.set_index("timestamp"); pos=g.position.reindex(m.index).ffill().fillna(0)
    hold=(pos.shift(1).fillna(0)*m.diff().fillna(0)).sum()   # PnL from holding inventory while price moves
    tot=g.pnl.iloc[-1]
    print(f"{day:>3} {p:14s} total {tot:8.0f}  from holding {hold:8.0f}  from trading edge {tot-hold:7.0f}  |pos| avg {pos.abs().mean():5.1f}  max {pos.abs().max():3.0f}")
