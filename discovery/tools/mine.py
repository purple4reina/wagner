"""Window hashing and information content for the n-gram mining steps (imported by s03+ and the explore scripts)."""
import numpy as np
from numba import njit

np.seterr(over="ignore")  # the polynomial hashes wrap around on purpose

B1 = np.uint64(1000003)
B2 = np.uint64(998244353)
M = np.uint64(0x9E3779B97F4A7C15)


def _prefix(tok, base):
    p = np.zeros(len(tok) + 1, dtype=np.uint64)
    t = tok.astype(np.uint64) + np.uint64(1)
    for i in range(len(tok)):  # sequential by nature; numpy cannot do a polynomial prefix directly
        p[i + 1] = p[i] * base + t[i]
    return p


class Hasher:
    """Hashes of windows of n notes: the n-1 intervals int_tok[s..s+n-2] and the n-2 rhythm classes rc[s+1..s+n-2]."""

    def __init__(self, int_tok, rc, seg):
        self.n_notes = len(int_tok)
        self.seg = seg
        self.Pi = _prefix(int_tok, B1)
        self.Pr = _prefix(rc, B2)
        self.int_tok, self.rc = int_tok, rc
        self.pw1 = [np.uint64(1)]
        self.pw2 = [np.uint64(1)]
        for _ in range(64):
            self.pw1.append(self.pw1[-1] * B1)
            self.pw2.append(self.pw2[-1] * B2)

    def starts(self, n):
        """Start indices of all valid windows of n notes (all in one segment)."""
        N = self.n_notes
        if N < n:
            return np.zeros(0, dtype=np.int64)
        s = np.arange(0, N - n + 1)
        return s[self.seg[s] == self.seg[s + n - 1]]

    def keys(self, n, s, use_rhythm=True):
        li, lr = n - 1, n - 2
        hi = self.Pi[s + li] - self.Pi[s] * self.pw1[li]
        if not use_rhythm:
            return hi
        hr = self.Pr[s + 1 + lr] - self.Pr[s + 1] * self.pw2[lr]
        return hi * M + hr


def surprisal(tok, valid, size):
    """-log2 relative frequency of each token value (over valid positions) -> per-position bits."""
    counts = np.bincount(tok[valid], minlength=size).astype(float)
    p = counts / counts.sum()
    bits = np.zeros(size)
    nz = counts > 0
    bits[nz] = -np.log2(p[nz])
    return bits[tok]


def window_ic(bits_i, bits_r, s, n):
    """Information content of a window: sum of interval bits [s, s+n-2] plus rhythm bits [s+1, s+n-2]."""
    ci = np.concatenate([[0.0], np.cumsum(bits_i)])
    cr = np.concatenate([[0.0], np.cumsum(bits_r)])
    return (ci[s + n - 1] - ci[s]) + (cr[s + n - 1] - cr[s + 1])


@njit(cache=True)
def _cluster(order_key_change, act, ts, te, gap, out):
    """Number clusters in windows already sorted by (key, act, t). A new cluster starts at a new key, a new act, or
    when the window starts more than `gap` quarter notes after the end of everything in the current cluster."""
    cur = -1
    end = -1e18
    for i in range(len(ts)):
        if order_key_change[i] or act[i] != act[i - 1] or ts[i] > end + gap:
            cur += 1
            end = te[i]
        else:
            if te[i] > end:
                end = te[i]
        out[i] = cur
    return cur + 1


def group_clusters(keys, act, ts, te, gap=4.0):
    """Sort windows by (key, act, start time) and number the clusters of overlapping or neighbouring windows.
    Returns (order, cluster_of_sorted, group_of_sorted) where `order` indexes the input arrays."""
    order = np.lexsort((ts, act, keys))
    k = keys[order]
    change = np.ones(len(k), dtype=np.bool_)
    change[1:] = k[1:] != k[:-1]
    cl = np.zeros(len(k), dtype=np.int64)
    _cluster(change, act[order].astype(np.int64), ts[order], te[order], gap, cl)
    grp = np.cumsum(change) - 1
    return order, cl, grp


def markov_bits(tok, seg, size, skip=None):
    """Bits of each token under interpolated unigram/bigram/trigram models of the corpus itself.
    Returns (b0, b1, b2): bits of token i given no context, the previous token, the two previous tokens.
    Tokens equal to `skip` (the "no value" code) and positions whose context crosses a segment are left at 0 bits."""
    P0, P1, P2, ok0, t = markov_tables(tok, seg, size, skip)
    N = len(tok)
    b0 = np.zeros(N); b1 = np.zeros(N); b2 = np.zeros(N)
    ok1 = ok0.copy(); ok1[1:] &= (seg[1:] == seg[:-1]) & ok0[:-1]; ok1[0] = False
    ok2 = ok1.copy(); ok2[2:] &= ok1[1:-1]; ok2[:2] = False
    b0[ok0] = -np.log2(P0[t[ok0]])
    i1 = np.nonzero(ok1)[0]
    b1[i1] = -np.log2(P1[t[i1 - 1], t[i1]])
    i2 = np.nonzero(ok2)[0]
    b2[i2] = -np.log2(P2[t[i2 - 2], t[i2 - 1], t[i2]])
    return b0, b1, b2


def markov_tables(tok, seg, size, skip=None):
    """Interpolated unigram/bigram/trigram probability tables P0[c], P1[b,c], P2[a,b,c] of the corpus itself."""
    N = len(tok)
    t = tok.astype(np.int64)
    ok0 = np.ones(N, bool) if skip is None else (t != skip)
    ok1 = ok0.copy(); ok1[1:] &= (seg[1:] == seg[:-1]) & ok0[:-1]; ok1[0] = False
    ok2 = ok1.copy(); ok2[2:] &= ok1[1:-1]; ok2[:2] = False
    C0 = np.bincount(t[ok0], minlength=size).astype(float)
    C1 = np.zeros((size, size)); np.add.at(C1, (t[:-1][ok1[1:]], t[1:][ok1[1:]]), 1)
    C2 = np.zeros((size, size, size)); np.add.at(C2, (t[:-2][ok2[2:]], t[1:-1][ok2[2:]], t[2:][ok2[2:]]), 1)
    P0 = (C0 + 0.5) / (C0.sum() + 0.5 * size)
    P1 = (C1 + 0.1 * P0[None, :]) / (C1.sum(1, keepdims=True) + 0.1)
    P2 = (C2 + 0.1 * P1[None, :, :].repeat(size, 0)) / (C2.sum(2, keepdims=True) + 0.1)
    return P0, P1, P2, ok0, t


def window_ic2(bi, br, s, n):
    """Information content of a window of n notes under the order-2 models: intervals s..s+n-2 get b0, b1, b2, b2, ...;
    rhythm classes s+1..s+n-2 likewise. A window that is a repeated cell, a trill or a scale scores low."""
    def one(b, a, e):  # tokens a..e inclusive
        b0, b1, b2 = b
        cs = np.concatenate([[0.0], np.cumsum(b2)])
        out = b0[a].copy()
        m = e > a
        out = out + np.where(m, b1[np.minimum(a + 1, len(b1) - 1)], 0.0)
        m2 = e > a + 1
        out = out + np.where(m2, cs[np.where(m2, e + 1, 0)] - cs[np.where(m2, a + 2, 0)], 0.0)
        return out
    return one(bi, s, s + n - 2) + (one(br, s + 1, s + n - 2) if n > 2 else 0.0)
