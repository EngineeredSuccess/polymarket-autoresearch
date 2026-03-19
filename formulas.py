import numpy as np
from scipy.special import rel_entr
import cvxpy as cp


def lmsr_price(q: np.ndarray, b: float) -> np.ndarray:
    """
    LMSR (Logarithmic Market Scoring Rule) pricing formula.

    Price_i = e^{q_i / b} / Σ e^{q_j / b}

    Args:
        q: Array of current shares for each outcome
        b: Liquidity parameter (higher = more stable prices)

    Returns:
        Array of prices for each outcome
    """
    q = np.array(q, dtype=float)
    exp_q_b = np.exp(q / b)
    return exp_q_b / np.sum(exp_q_b)


def lmsr_price_impact(q: np.ndarray, b: float, buy_shares: np.ndarray) -> tuple:
    """
    Calculate price impact from buying shares.

    Args:
        q: Current shares
        b: Liquidity parameter
        buy_shares: Number of shares to buy for each outcome

    Returns:
        (prices_before, prices_after, price_change)
    """
    prices_before = lmsr_price(q, b)
    q_after = q + buy_shares
    prices_after = lmsr_price(q_after, b)
    return prices_before, prices_after, prices_after - prices_before


def kelly_fraction(p: float, price: float, kelly_mult: float = 1.0) -> float:
    """
    Kelly Criterion for optimal bet sizing.

    f* = (p * odds - (1-p)) / odds
    where odds = 1/price - 1

    Args:
        p: True probability (your estimate)
        price: Current market price
        kelly_mult: Multiplier for fractional Kelly (default 1.0)

    Returns:
        Fraction of bankroll to bet (0 if negative)
    """
    if price <= 0 or price >= 1:
        return 0.0

    odds = (1 / price) - 1
    if odds <= 0:
        return 0.0

    kelly = (p * odds - (1 - p)) / odds
    kelly = kelly * kelly_mult

    return max(0.0, kelly)


def kelly_bet_size(
    p: float, price: float, bankroll: float, kelly_mult: float = 0.5
) -> float:
    """
    Calculate dollar amount to bet using Kelly Criterion.

    Args:
        p: True probability
        price: Market price
        bankroll: Current bankroll
        kelly_mult: Fractional Kelly multiplier

    Returns:
        Dollar amount to bet
    """
    fraction = kelly_fraction(p, price, kelly_mult)
    return bankroll * fraction


def ev_gap(p_true: float, price: float) -> float:
    """
    Expected Value Gap - measures mispricing.

    EV = (p_true - price) * (1/price)

    Args:
        p_true: Your estimated true probability
        price: Current market price

    Returns:
        Expected value as decimal (positive = edge)
    """
    if price <= 0:
        return 0.0
    return (p_true - price) * (1 / price)


def ev_recommendation(p_true: float, price: float, min_ev: float = 0.05) -> dict:
    """
    Generate bet recommendation based on EV gap.

    Args:
        p_true: True probability
        price: Market price
        min_ev: Minimum EV threshold

    Returns:
        dict with ev, recommendation, stake for $1K
    """
    ev = ev_gap(p_true, price)
    recommend = ev > min_ev
    stake_1k = 1000 * recommend

    return {
        "ev": ev,
        "recommend": recommend,
        "stake_1000": stake_1k,
        "verdict": "BET" if recommend else "PASS",
    }


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """
    KL-Divergence for comparing probability distributions.

    D_KL(P||Q) = Σ P_i * log(P_i / Q_i)

    Args:
        p: True/actual distribution
        q: Model/expected distribution

    Returns:
        KL divergence value
    """
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)

    p = np.clip(p, 1e-10, 1.0)
    q = np.clip(q, 1e-10, 1.0)

    return np.sum(rel_entr(p, q))


def kl_arbitrage_opportunity(
    p: np.ndarray, q: np.ndarray, threshold: float = 0.2
) -> dict:
    """
    Detect arbitrage opportunity using KL-Divergence.

    Args:
        p: Your estimated distribution
        q: Market distribution
        threshold: KL threshold for signaling

    Returns:
        dict with kl_value, is_arb, interpretation
    """
    kl = kl_divergence(p, q)

    return {
        "kl_value": kl,
        "is_arb": kl > threshold,
        "threshold": threshold,
        "interpretation": "HEDGE OPPORTUNITY"
        if kl > threshold
        else "No significant arb",
    }


def bregman_projection_kl(theta: np.ndarray, constraints: dict = None) -> np.ndarray:
    """
    Bregman Projection with KL-divergence for multi-outcome arbitrage.

    Minimizes D_φ(μ||θ) subject to constraints.

    Args:
        theta: Initial probability distribution
        constraints: Dict with 'eq' (equality) and 'ineq' constraints

    Returns:
        Projected distribution μ
    """
    theta = np.array(theta, dtype=float)
    n = len(theta)

    mu = cp.Variable(n)
    objective = cp.Minimize(cp.sum(cp.rel_entr(mu, theta)))
    constraints = [cp.sum(mu) == 1, mu >= 0.01]

    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.SCS)

    return mu.value


def find_arb_bregman(prices: np.ndarray, true_probs: np.ndarray) -> dict:
    """
    Find arbitrage opportunity using Bregman Projection.

    Args:
        prices: Market prices
        true_probs: Your estimated true probabilities

    Returns:
        dict with arb_exists, projected_probs, edge
    """
    projected = bregman_projection_kl(true_probs)

    if projected is None:
        return {"arb_exists": False, "edge": 0.0}

    edge = np.sum(projected - prices)

    return {
        "arb_exists": edge > 0.01,
        "projected_probs": projected,
        "edge": edge,
        "interpretation": "RISK-FREE EDGE" if edge > 0.01 else "No arb",
    }


def bayesian_update(prior: float, likelihood: float, evidence_prob: float) -> float:
    """
    Bayesian Update formula.

    P(H|E) = P(E|H) * P(H) / P(E)

    Args:
        prior: P(H) - prior probability of hypothesis
        likelihood: P(E|H) - probability of evidence given hypothesis
        evidence_prob: P(E) - probability of evidence

    Returns:
        Posterior probability P(H|E)
    """
    if evidence_prob <= 0:
        return prior

    posterior = (likelihood * prior) / evidence_prob
    return min(1.0, max(0.0, posterior))


def bayesian_chain_update(
    prior: float, evidence_likelihoods: list, evidence_probs: list
) -> float:
    """
    Chain multiple Bayesian updates.

    Args:
        prior: Initial prior probability
        evidence_likelihoods: List of P(E_i|H) for each evidence
        evidence_probs: List of P(E_i) for each evidence

    Returns:
        Updated posterior after all evidence
    """
    posterior = prior

    for likelihood, prob_evidence in zip(evidence_likelihoods, evidence_probs):
        posterior = bayesian_update(posterior, likelihood, prob_evidence)

    return posterior


def bayesian_sentiment_update(
    prior: float, sentiment_score: float, strength: float = 0.1
) -> float:
    """
    Simplified Bayesian update using sentiment score.

    Args:
        prior: Prior probability
        sentiment_score: -1 to 1 (negative to positive sentiment)
        strength: How much to weight the sentiment (0-1)

    Returns:
        Updated probability
    """
    likelihood = 0.5 + (sentiment_score * strength)
    evidence_prob = 0.5

    return bayesian_update(prior, likelihood, evidence_prob)


def compute_all_signals(market_data: dict) -> dict:
    """
    Compute all 6 formula signals for a market.

    Args:
        market_data: dict with:
            - price: market price
            - volume: trading volume
            - b: liquidity parameter
            - q: current shares (optional)
            - my_p: your true probability estimate
            - bankroll: current bankroll
            - correlated_market: dict with correlated market data

    Returns:
        dict with all computed signals
    """
    price = market_data.get("price", 0.5)
    b = market_data.get("b", 100)
    q = market_data.get("q", np.array([0, 0]))
    my_p = market_data.get("my_p", price)
    bankroll = market_data.get("bankroll", 10000)
    correlated_p = market_data.get("correlated_p", np.array([price, 1 - price]))

    prices_before, prices_after, price_impact = lmsr_price_impact(
        q, b, np.array([10, 0])
    )

    kelly_frac = kelly_fraction(my_p, price, kelly_mult=0.5)
    kelly_dollars = kelly_frac * bankroll

    ev = ev_gap(my_p, price)
    ev_rec = ev_recommendation(my_p, price)

    market_p = np.array([price, 1 - price])
    kl_result = kl_arbitrage_opportunity(correlated_p, market_p)

    bregman_result = find_arb_bregman(market_p, correlated_p)

    bayes_result = bayesian_chain_update(
        prior=price,
        evidence_likelihoods=[0.7, 0.8, 0.6],
        evidence_probs=[0.5, 0.5, 0.5],
    )

    return {
        "lmsr": {
            "price_before": prices_before[0],
            "price_after": prices_after[0],
            "price_impact": price_impact[0],
        },
        "kelly": {"fraction": kelly_frac, "bet_size": kelly_dollars},
        "ev_gap": {
            "ev": ev,
            "recommendation": ev_rec["verdict"],
            "stake": ev_rec["stake_1000"],
        },
        "kl_divergence": kl_result,
        "bregman": bregman_result,
        "bayesian": {"prior": price, "posterior": bayes_result, "update_applied": 3},
    }
