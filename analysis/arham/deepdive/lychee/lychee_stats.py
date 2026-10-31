import math, random, statistics as st
from load import load
mids, book, trades = load()
days = (-2, -1, 0)
X = {d: [mids[d]["LYCHEE"][t] for t in sorted(mids[d]["LYCHEE"])] for d in days}
full = X[-2] + X[-1] + X[0]

def ols(y, cols):
    # least squares with intercept-free design matrix cols (list of columns); returns beta, se
    n, k = len(y), len(cols)
    A = [[sum(cols[i][r] * cols[j][r] for r in range(n)) for j in range(k)] for i in range(k)]
    b = [sum(cols[i][r] * y[r] for r in range(n)) for i in range(k)]
    # invert A (small k) by Gauss-Jordan
    M = [row[:] + [1.0 if i == j else 0.0 for j in range(k)] for i, row in enumerate(A)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]
        pv = M[c][c]; M[c] = [v / pv for v in M[c]]
        for r in range(k):
            if r != c:
                f = M[r][c]; M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    inv = [row[k:] for row in M]
    beta = [sum(inv[i][j] * b[j] for j in range(k)) for i in range(k)]
    res = [y[r] - sum(beta[i] * cols[i][r] for i in range(k)) for r in range(n)]
    s2 = sum(e * e for e in res) / (n - k)
    se = [math.sqrt(s2 * inv[i][i]) for i in range(k)]
    return beta, se

def adf_t(x, lags=2):
    dx = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    y = dx[lags:]; n = len(y)
    cols = [[1.0] * n, x[lags:-1]] + [dx[lags - j - 1: len(dx) - j - 1] for j in range(lags)]
    beta, se = ols(y, cols)
    return beta[1] / se[1], beta

def vr(x, q, base=10):
    xb = x[::base]; c1 = [xb[i + 1] - xb[i] for i in range(len(xb) - 1)]
    m = q // base; cq = [xb[i + m] - xb[i] for i in range(0, len(xb) - m, m)]
    return st.pvariance(cq) / (m * st.pvariance(c1))

def stats(series_by_day, k=100):
    pooled = []
    for d in days: pooled += series_by_day[d]
    s = pooled[::k]
    t, beta = adf_t(s)
    return t, vr(pooled, 1000), vr(pooled, 3000)

t_obs, vr1k, vr3k = stats(X)
print(f"OBSERVED (all 3 days, sampled every 100 ticks): ADF t = {t_obs:.2f}  (5% critical -2.86, 1% -3.43)  VR(1000) {vr1k:.2f}  VR(3000) {vr3k:.2f}")
for d in days:
    s = X[d][::100]; t, beta = adf_t(s)
    a, b = beta[0], 1 + beta[1]
    print(f"  day {d}: ADF t {t:.2f}   OU fit: mean {a / (1 - b):.0f}, half-life {math.log(.5) / math.log(b) * 100 if 0 < b < 1 else float('inf'):.0f} ticks, day mean {st.mean(X[d]):.0f}, range {min(X[d]):.0f}-{max(X[d]):.0f}")
# realized vol per day-equivalent at several horizons vs. what the vouchers imply (~2.1% * 7450 = ~157/day)
for k in (10, 100, 1000, 3000):
    ch = [full[i + k] - full[i] for i in range(0, len(full) - k, k)]
    print(f"  realized daily-equivalent sd from {k:5d}-tick moves: {st.pstdev(ch) * math.sqrt(10000 / k):6.1f}  (n={len(ch)})")

# Monte Carlo: pure random walks with the same 10-tick step size + the same tick bounce
step10 = st.pstdev([full[i + 10] - full[i] for i in range(0, len(full) - 10, 10)])
random.seed(1)
sims = []
for _ in range(400):
    sd = {}
    for d in days:
        x = []; v = 7450.0 if d == -2 else sd[d - 1][-1]
        for i in range(10000):
            if i % 10 == 0: v += random.gauss(0, step10)
            x.append(v)
        sd[d] = x
    sims.append(stats(sd))
p_adf = sum(s[0] <= t_obs for s in sims) / len(sims)
p_vr1 = sum(s[1] <= vr1k for s in sims) / len(sims)
p_vr3 = sum(s[2] <= vr3k for s in sims) / len(sims)
print(f"MONTE CARLO (400 pure random walks, 3 days each): share at least as 'leashed' as LYCHEE -> ADF {p_adf:.1%}, VR(1000) {p_vr1:.1%}, VR(3000) {p_vr3:.1%}")
