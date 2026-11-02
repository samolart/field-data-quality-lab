"""Minimal, dependency-light statistics toolkit (NumPy/SciPy/pandas only).

Why hand-rolled? The pipeline must run anywhere with a plain scientific-Python install, and every
estimator here is short enough to audit line by line - which is the point for a research-data team.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------- design matrices
def design(df: pd.DataFrame, cols: list[str], fe: list[str] | None = None) -> pd.DataFrame:
    X = df[cols].astype(float).copy() if cols else pd.DataFrame(index=df.index)
    for f in fe or []:
        X = pd.concat([X, pd.get_dummies(df[f].astype("category"), prefix=f, drop_first=True, dtype=float)], axis=1)
    X.insert(0, "const", 1.0)
    keep = ["const"] + [c for c in X.columns if c != "const" and X[c].std() > 0]
    return X[keep]


# ---------------------------------------------------------------- OLS
def ols(y, X: pd.DataFrame, cluster=None) -> dict:
    """OLS with HC1 or CR1 (cluster) variance. Rank-deficient designs handled via pinv."""
    y = np.asarray(y, float)
    Xv = X.to_numpy(float)
    n, k = Xv.shape
    xtx_inv = np.linalg.pinv(Xv.T @ Xv)
    b = xtx_inv @ Xv.T @ y
    u = y - Xv @ b
    if cluster is None:
        meat = (Xv * u[:, None]).T @ (Xv * u[:, None])
        scale, df = n / (n - k), n - k
    else:
        cl = pd.factorize(np.asarray(cluster))[0]
        G = cl.max() + 1
        S = np.zeros((G, k))
        np.add.at(S, cl, Xv * u[:, None])
        meat = S.T @ S
        scale, df = (G / (G - 1)) * ((n - 1) / (n - k)), G - 1
    V = scale * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = b / se
    p = 2 * stats.t.sf(np.abs(t), df)
    ss_res, ss_tot = float(u @ u), float(((y - y.mean()) ** 2).sum())
    return dict(names=list(X.columns), b=b, se=se, t=t, p=p, V=V, n=n, k=k, df=df,
                r2=1 - ss_res / ss_tot if ss_tot > 0 else np.nan, resid=u)


def coef(res: dict, name: str) -> tuple[float, float, float]:
    i = res["names"].index(name)
    return res["b"][i], res["se"][i], res["p"][i]


def wald_joint(res: dict, names: list[str]) -> tuple[float, float]:
    """Joint F-test that the named coefficients are all zero (robust)."""
    idx = [res["names"].index(n) for n in names if n in res["names"]]
    b, V = res["b"][idx], res["V"][np.ix_(idx, idx)]
    q = len(idx)
    F = float(b @ np.linalg.pinv(V) @ b) / q
    return F, float(stats.f.sf(F, q, res["df"]))


# ---------------------------------------------------------------- multiple testing
def holm(p) -> np.ndarray:
    p = np.asarray(p, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * p[i])
        adj[i] = min(1.0, run)
    return adj


def bh(p) -> np.ndarray:
    """Benjamini-Hochberg q-values."""
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    q = np.empty(m)
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        prev = min(prev, p[i] * m / (rank + 1))
        q[i] = prev
    return q


# ---------------------------------------------------------------- Lee (2009) bounds, binary outcome
def lee_bounds(y, treat, selected, n_boot=500, seed=1):
    """Trimming bounds for the ITT effect on a binary outcome under differential selection (attrition)."""
    y, t, s = (np.asarray(a, float) for a in (y, treat, selected))

    def one(y, t, s):
        p1, p0 = s[t == 1].mean(), s[t == 0].mean()
        y1, y0 = y[(t == 1) & (s == 1)], y[(t == 0) & (s == 1)]
        if p1 >= p0:  # trim treated
            q = (p1 - p0) / p1
            n1 = len(y1); k = int(round(q * n1))
            ys = np.sort(y1)
            lo = ys[: n1 - k].mean() - y0.mean()   # drop the top k
            hi = ys[k:].mean() - y0.mean()         # drop the bottom k
        else:          # trim control
            q = (p0 - p1) / p0
            n0 = len(y0); k = int(round(q * n0))
            ys = np.sort(y0)
            lo = y1.mean() - ys[k:].mean()
            hi = y1.mean() - ys[: n0 - k].mean()
        return lo, hi

    lo, hi = one(y, t, s)
    rng = np.random.default_rng(seed)
    n = len(y)
    bl, bhh = [], []
    for _ in range(n_boot):
        ix = rng.integers(0, n, n)
        a, b_ = one(y[ix], t[ix], s[ix])
        bl.append(a); bhh.append(b_)
    return lo, hi, np.percentile(bl, 2.5), np.percentile(bhh, 97.5)


# ---------------------------------------------------------------- misc
def has_token(series: pd.Series, token) -> pd.Series:
    """For SurveyCTO-style space-separated multi-select answers: 1/0, NaN if blank."""
    tok = str(token)

    def f(v):
        if pd.isna(v) or str(v).strip() == "":
            return np.nan
        return float(tok in str(v).split())

    return series.map(f)


def icc_anova(values: pd.Series, groups: pd.Series) -> tuple[float, float, float]:
    """ICC(1) from one-way ANOVA with unbalanced groups (Searle). Returns (icc, F, p)."""
    df = pd.DataFrame({"y": values, "g": groups}).dropna()
    k = df.g.nunique()
    n = len(df)
    ni = df.groupby("g").y.size()
    gm = df.y.mean()
    ssb = (ni * (df.groupby("g").y.mean() - gm) ** 2).sum()
    ssw = ((df.y - df.groupby("g").y.transform("mean")) ** 2).sum()
    msb, msw = ssb / (k - 1), ssw / (n - k)
    n0 = (n - (ni ** 2).sum() / n) / (k - 1)
    icc = (msb - msw) / (msb + (n0 - 1) * msw)
    F = msb / msw
    return float(icc), float(F), float(stats.f.sf(F, k - 1, n - k))
