"""ARHAM's products: DRAGONFRUIT, GRANADILLA, MANGOSTEEN, FRUIT_BASKET, LYCHEE, and the
10 LYCHEE vouchers (call options; symbols in the data are VOUCHER_6800 ... VOUCHER_8100).

Owner: Arham. Only Arham edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.

What the data showed (analysis/arham/NOTES.md has the numbers and plots):
  * Vouchers: priced like Black-Scholes calls whose implied vol sits on a smooth "smile"
    across strikes. Each voucher's price wanders a few coins off that smile and snaps back
    within a few hundred ticks, and the market's own trades lean the same way (about 90% of
    trades are buys when a voucher is cheap). So we buy cheap vouchers and sell rich ones.
  * LYCHEE, the three fruits and FRUIT_BASKET move like random walks (nothing predicts the
    next move, and the basket ~ 2 DRAGONFRUIT + 3 GRANADILLA + 1 MANGOSTEEN plus a gap that
    drifts instead of snapping back). Market trades in them happen at the best bid/ask and
    don't predict the next move, so we just sit on the best bid and ask to earn the spread,
    with small position caps because holding them is pure risk.
  * Over hours, though, LYCHEE gets pulled back toward a "home" price of about 7,436 (same
    home on all 3 days). So we lean the voucher book: hold up to +150 LYCHEE-equivalents when
    LYCHEE is 60+ below home and -150 when it's 60+ above (rotation test in
    analysis/arham/deepdive/rotation/ROTATION_TEST.md: improved every held-out day).
"""
import math
from typing import Dict, List, Optional

from datamodel import Order, OrderDepth, TradingState


class FruitLycheeStrategy:
    STRIKES = [6800, 7000, 7200, 7300, 7400, 7500, 7600, 7750, 7900, 8100]
    VOUCHERS = {f"VOUCHER_{k}": k for k in STRIKES}
    FRUITS = ["DRAGONFRUIT", "GRANADILLA", "MANGOSTEEN", "FRUIT_BASKET"]
    LIMITS = {
        "DRAGONFRUIT": 40,
        "GRANADILLA": 40,
        "MANGOSTEEN": 40,
        "FRUIT_BASKET": 40,
        "LYCHEE": 200,
        **{f"VOUCHER_{k}": 50 for k in STRIKES},
    }
    # Tuned on days -2/-1 and checked on day 0; results barely change for nearby values
    # (enter 3-4, exit 1-2, smile_halflife 150-400, flow_weight 0.3-0.5 all land within ~3%).
    PARAMS = {
        "days_to_expiry": 5,  # at the open of the scoring day (it was 8 at day -2, 7 at -1, 6 at 0)
        "smile_halflife": 200,  # ticks; how slowly our estimate of the fair vol smile moves
        "enter": 3.5,  # take a voucher position when the price is this many coins past fair value
        "exit": 1.5,  # close it once the price has come back past fair value by this much
        "flow_weight": 0.0,  # coins each recently traded unit moves fair value (buys up, sells down)
        "flow_halflife": 30,  # ticks; how fast we forget those trades
        "delta_skew": 0.05,  # shade fair values to steer our total LYCHEE exposure toward the lean target
        "skew_cap": 5.0,  # never shade a fair value by more than this many coins
        "lychee_cap": 10,  # quote LYCHEE on both sides, but never hold more than this past the target
        "fruit_cap": 1,  # same for each fruit and the basket
        "lean_size": 150,  # biggest LYCHEE bet (in LYCHEE-equivalents) on the price returning home
        "lean_width": 60,  # how far from home LYCHEE must be for the full bet
        "lean_home": 7435.9,  # LYCHEE's average price over days -2, -1, 0
        "lean_hold": 100000,  # the home also drifts very slowly toward the live price (ticks of weight)
    }

    def __init__(self, params: Optional[dict] = None):
        self.p = dict(self.PARAMS, **(params or {}))
        self.debug: Optional[list] = None  # analysis scripts set this to a list to record exposure

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        """Called every tick. Return {product: [Order, ...]}.
        `mem` is this file's private memory: whatever you put in it comes back next tick."""
        result: Dict[str, List[Order]] = self.vouchers(state, mem)
        center = max(-190, min(190, int(round(mem.get("target", 0)))))  # LYCHEE quotes lean the same way
        result["LYCHEE"] = self.join_quotes("LYCHEE", state, self.p["lychee_cap"], center)
        for sym in self.FRUITS:
            result[sym] = self.join_quotes(sym, state, self.p["fruit_cap"])
        return {sym: orders for sym, orders in result.items() if orders}

    # ------------------------------------------------------------------ vouchers
    def vouchers(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        S = self.mid(state.order_depths.get("LYCHEE"))
        if S is None:
            return {}
        T = max(self.p["days_to_expiry"] - state.timestamp / 1_000_000, 0.1)  # days left
        smile = mem.get("smile")  # [a, b, c]: fair vol = a + b*x + c*x^2, x = 100*ln(K/S)/sqrt(T)

        # 1. Each voucher's implied vol right now (the vol that makes Black-Scholes = its mid price)
        xs, ivs, mids = {}, {}, {}
        for sym, K in self.VOUCHERS.items():
            m = self.mid(state.order_depths.get(sym))
            if m is None:
                continue
            x = 100 * math.log(K / S) / math.sqrt(T)  # how far out of the money, in vol units
            guess = smile[0] + smile[1] * x + smile[2] * x * x if smile else 0.02
            iv = self.implied_vol(m, S, K, T, guess)
            mids[sym], xs[sym] = m, x
            if iv is not None:
                ivs[sym] = iv

        # 2. Fit one smooth smile through all strikes, then average it over recent ticks.
        #    Each strike's own wobble is independent of the others', so the fit averages it out.
        if len(ivs) >= 5:
            fit = self.fit_parabola([xs[sym] for sym in ivs], list(ivs.values()))
            if fit is not None:
                n = mem.get("n", 0) + 1
                a = max(1 - 0.5 ** (1 / self.p["smile_halflife"]), 1 / n)  # plain mean while warming up
                smile = fit if smile is None else [old + a * (new - old) for old, new in zip(smile, fit)]
                mem["smile"], mem["n"] = smile, n
        if smile is None:
            return {}

        # 3. Recent market trades: buyers show up when a voucher is cheap, sellers when it's rich.
        #    flow = recent units bought minus units sold (fading out), nudges fair value that way.
        flow = mem.setdefault("flow", {})
        last_mid = mem.setdefault("mid", {})
        decay = 0.5 ** (1 / self.p["flow_halflife"])
        market_trades = state.market_trades or {}
        for sym in self.VOUCHERS:
            f = flow.get(sym, 0.0) * decay
            for tr in market_trades.get(sym, []) or []:
                if sym in last_mid:
                    f += tr.quantity if tr.price > last_mid[sym] else -tr.quantity
            flow[sym] = round(f, 3)
        last_mid.update(mids)

        # 4. Our total exposure to LYCHEE moves (each voucher moves `delta` coins per coin of LYCHEE).
        #    When it's large, we shade every voucher's fair value so new trades shrink it.
        vols = {sym: smile[0] + smile[1] * x + smile[2] * x * x for sym, x in xs.items()}
        deltas = {sym: self.bs_delta(S, self.VOUCHERS[sym], T, vols[sym]) for sym in xs}
        exposure = state.position.get("LYCHEE", 0) + sum(
            state.position.get(sym, 0) * d for sym, d in deltas.items())

        #    The exposure we steer toward isn't 0: lean against LYCHEE's distance from home
        #    (+lean_size when it's lean_width or more below home, -lean_size when as far above).
        n_home = mem.get("home_n", 0) + 1
        home = mem.get("home", self.p["lean_home"])
        home += (S - home) / (self.p["lean_hold"] + n_home)
        mem["home"], mem["home_n"] = home, n_home
        target = -self.p["lean_size"] * max(-1.0, min(1.0, (S - home) / self.p["lean_width"]))
        mem["target"] = target

        # 5. Fair price = Black-Scholes at the smile's vol (+ flow and exposure nudges); trade the gap
        out, fairs = {}, {}
        cap = self.p["skew_cap"]
        for sym in xs:
            K = self.VOUCHERS[sym]
            fair = self.bs_call(S, K, T, vols[sym]) + self.p["flow_weight"] * flow[sym]
            fair -= max(-cap, min(cap, self.p["delta_skew"] * (exposure - target) * deltas[sym]))
            fairs[sym] = fair
            out[sym] = self.revert(sym, state.position.get(sym, 0), self.LIMITS[sym], fair)
        if self.debug is not None:
            self.debug.append({
                "t": state.timestamp, "S": S, "exposure": exposure, "smile": list(smile),
                "x": xs, "mid": mids, "fair": fairs,
                "delta_pos": {sym: state.position.get(sym, 0) * d for sym, d in deltas.items()},
            })
        return out

    def revert(self, sym: str, pos: int, limit: int, fair: float) -> List[Order]:
        """Bet on the price snapping back to fair. One order per job, each at the worst price
        we'd accept: the exchange fills it against every better-priced quote in the book, and
        whatever's left can still fill against this tick's market trades.
          buy  up to the limit at  fair - enter   (clearly cheap: get long)
          sell up to the limit at  fair + enter   (clearly rich: get short)
          close a short at fair - exit, close a long at fair + exit (price has come back)"""
        enter, exit_ = self.p["enter"], self.p["exit"]
        can_buy, can_sell = limit - pos, limit + pos
        close_short = min(can_buy, max(-pos, 0))
        close_long = min(can_sell, max(pos, 0))
        orders = []
        if close_short:
            orders.append(Order(sym, math.floor(fair - exit_), close_short))
        if can_buy > close_short:
            orders.append(Order(sym, math.floor(fair - enter), can_buy - close_short))
        if close_long:
            orders.append(Order(sym, math.ceil(fair + exit_), -close_long))
        if can_sell > close_long:
            orders.append(Order(sym, math.ceil(fair + enter), -(can_sell - close_long)))
        return orders

    @staticmethod
    def fit_parabola(xs: List[float], ys: List[float]) -> Optional[List[float]]:
        """Least-squares y = a + b*x + c*x^2 (solves the 3x3 normal equations with Cramer's rule)."""
        s = [sum(x ** k for x in xs) for k in range(5)]
        t = [sum(y * x ** k for x, y in zip(xs, ys)) for k in range(3)]
        A = [[s[0], s[1], s[2]], [s[1], s[2], s[3]], [s[2], s[3], s[4]]]

        def det(M):
            return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
                    - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
                    + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))

        D = det(A)
        if abs(D) < 1e-12:
            return None
        out = []
        for col in range(3):
            M = [row[:] for row in A]
            for r in range(3):
                M[r][col] = t[r]
            out.append(det(M) / D)
        return out

    # ------------------------------------------------------------------ LYCHEE, fruits, basket
    def join_quotes(self, sym: str, state: TradingState, cap: int, center: int = 0) -> List[Order]:
        """Sit on the best bid and the best ask. Market trades happen at exactly those prices,
        so each one that hits us earns half the spread. Quote sizes shrink as we build a
        position, so it never goes past center +- cap."""
        depth = state.order_depths.get(sym)
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return []
        pos = state.position.get(sym, 0)
        orders = []
        if center + cap - pos > 0:
            orders.append(Order(sym, max(depth.buy_orders), center + cap - pos))
        if cap + pos - center > 0:
            orders.append(Order(sym, min(depth.sell_orders), -(cap + pos - center)))
        return orders

    # ------------------------------------------------------------------ math helpers
    @staticmethod
    def mid(depth: Optional[OrderDepth]) -> Optional[float]:
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return None
        return (max(depth.buy_orders) + min(depth.sell_orders)) / 2

    @staticmethod
    def bs_call(S: float, K: float, T: float, vol: float) -> float:
        """Black-Scholes call price (no interest rate); T in days, vol per sqrt(day)."""
        sd = vol * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sd * sd) / sd
        d2 = d1 - sd
        return S * 0.5 * (1 + math.erf(d1 / math.sqrt(2))) - K * 0.5 * (1 + math.erf(d2 / math.sqrt(2)))

    @staticmethod
    def bs_delta(S: float, K: float, T: float, vol: float) -> float:
        """How many coins the call moves per coin LYCHEE moves."""
        sd = vol * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sd * sd) / sd
        return 0.5 * (1 + math.erf(d1 / math.sqrt(2)))

    @staticmethod
    def bs_vega(S: float, K: float, T: float, vol: float) -> float:
        """How many coins the call moves per unit of vol."""
        sd = vol * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sd * sd) / sd
        return S * math.sqrt(T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)

    @classmethod
    def implied_vol(cls, price: float, S: float, K: float, T: float, guess: float) -> Optional[float]:
        """The vol that makes Black-Scholes match `price` (Newton's method from `guess`)."""
        if price <= max(S - K, 0) + 0.01 or price >= S:
            return None
        vol = guess
        for _ in range(20):
            diff = cls.bs_call(S, K, T, vol) - price
            if abs(diff) < 1e-4:
                return vol
            vega = cls.bs_vega(S, K, T, vol)
            if vega < 1e-6:
                return None
            vol = min(max(vol - diff / vega, 1e-4), 0.5)
        return vol if abs(cls.bs_call(S, K, T, vol) - price) < 0.05 else None
