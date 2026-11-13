"""Transforms, the model form, and the fitting routine used across the project."""
import numpy as np
from scipy.optimize import nnls
from sklearn.linear_model import LinearRegression


def adstock(x, decay):
    """Geometric carry-over: this week's pressure plus a share of last week's."""
    out = np.empty_like(x, dtype=float)
    run = 0.0
    for i, v in enumerate(x):
        run = v + decay * run
        out[i] = run
    return out


def hill(x, shape, half):
    """Diminishing returns: half the maximum effect is reached at `half`."""
    xs = np.power(np.maximum(x, 0.0), shape)
    return xs / (xs + half ** shape)


def transform(spend, decay, shape, half_mult):
    """Spend to saturated pressure. The half-saturation point is set in units of average pressure."""
    ad = adstock(spend, decay)
    half = max(half_mult * ad.mean(), 1e-6)
    return hill(ad, shape, half), half


def base_design(d, harmonics=3):
    """
    Everything that moves sales and is not media: a trend, an annual shape,
    the holiday peak, and how deeply the range was discounted that week.
    """
    woy = d.week_of_year.to_numpy()
    cols = {"trend": d.t.to_numpy() / 52.0}
    for k in range(1, harmonics + 1):
        cols[f"sin{k}"] = np.sin(2 * np.pi * k * woy / 52.18)
        cols[f"cos{k}"] = np.cos(2 * np.pi * k * woy / 52.18)
    cols["peak_holiday"] = d.peak_holiday.to_numpy(float)
    cols["back_to_school"] = d.back_to_school.to_numpy(float)
    cols["price_index"] = (d.price_index.to_numpy() - d.price_index.mean()) / d.price_index.std()
    names = list(cols)
    return np.column_stack([cols[n] for n in names]), names


def fit_mmm(y, B, S, beta_init=None, prior_share=None, lam=0.0, calibration=None, iters=80, tol=1e-10):
    """
    Sales = base x (1 + sum of channel lifts), with the base a log-linear function
    of trend, season, holidays and price.

    The two halves are fitted in turn. Channel coefficients cannot go negative.

    prior_share / lam  pull the split of contribution toward the split of spend,
                       which is what a planner would assume with no other evidence.
    calibration        a list of (channel index, measured incremental revenue,
                       standard error, week mask) from an experiment. Each one
                       pins that channel, leaving the rest to the data.
    """
    n_ch = S.shape[1]
    beta = np.zeros(n_ch) if beta_init is None else np.array(beta_init, float)
    theta = np.zeros(B.shape[1] + 1)
    for _ in range(iters):
        lr = LinearRegression().fit(B, np.log(y / np.maximum(1.0 + S @ beta, 1e-6)))
        theta = np.r_[lr.intercept_, lr.coef_]
        base = np.exp(theta[0] + B @ theta[1:])
        A = S * base[:, None]
        # Put every block in the same units before stacking: the model rows are
        # scaled by the residual noise, the experiment rows by their own standard
        # error. Without this the test is outvoted by the history it is meant to
        # correct.
        sigma = max(float(np.std(y - base * (1.0 + S @ beta))), 1e-6)
        rows, targets = [A / sigma], [(y - base) / sigma]
        if lam > 0 and prior_share is not None:
            w = A.mean(0)                                        # contribution dollars per unit beta
            total = max((y - base).mean(), 0.0)
            b0 = prior_share * total / np.maximum(w, 1e-9)
            rows.append(np.sqrt(lam) * np.diag(w) / sigma)
            targets.append(np.sqrt(lam) * w * b0 / sigma)
        for idx, measured, se, mask in (calibration or []):
            row = np.zeros(n_ch)
            row[idx] = A[mask, idx].sum()
            rows.append((row / se)[None, :])
            targets.append(np.array([measured / se]))
        new_beta, _ = nnls(np.vstack(rows), np.concatenate(targets))
        if np.allclose(new_beta, beta, atol=tol):
            beta = new_beta
            break
        beta = new_beta
    base = np.exp(theta[0] + B @ theta[1:])
    fitted = base * (1.0 + S @ beta)
    return {"theta": theta, "beta": beta, "base": base, "fitted": fitted,
            "contrib": base[:, None] * S * beta,
            "r2": float(1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum())}
