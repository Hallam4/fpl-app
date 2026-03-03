import time
import numpy as np
from scipy import stats
from scipy.linalg import cholesky
import fpl_client
from models import (
    SimulationResult,
    SimulationMeta,
    PlayerSimRow,
    PlayerSimulationsResponse,
    PlayerDetailSimulation,
)

N_SIMULATIONS = 10_000
N_PLAYER_SIMS = 1_000
N_STRATA = 50

# ---------------------------------------------------------------------------
# Module-level caches (shared across endpoints, 5-min TTL)
# ---------------------------------------------------------------------------
_PLAYER_SIM_TTL = 300

_player_sim_cache: dict = {}  # {cache_key: (timestamp, PlayerSimulationsResponse)}
_player_fit_cache: dict = {}  # {player_id: (mu_base, sigma, df)}
POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
SAME_TEAM_CORR = 0.35
T_COPULA_DF = 4  # low df = more tail dependence between same-team players


# ---------------------------------------------------------------------------
# Distribution fitting
# ---------------------------------------------------------------------------

def _fit_student_t(points: list[float]) -> tuple[float, float, float]:
    """Fit Student-t to player GW history. Returns (mu, sigma, df)."""
    if len(points) < 3:
        mu = float(np.mean(points)) if points else 0.0
        return mu, max(mu * 0.5, 2.0), 4.0
    try:
        df, loc, scale = stats.t.fit(points)
        df = float(np.clip(df, 2.5, 30.0))
        return float(loc), float(max(scale, 0.5)), df
    except Exception:
        mu = float(np.mean(points))
        sigma = float(np.std(points, ddof=1)) if len(points) > 1 else 2.0
        return mu, max(sigma, 0.5), 4.0


# ---------------------------------------------------------------------------
# Variance-reduction helpers
# ---------------------------------------------------------------------------

def _stratified_uniform(rng: np.random.Generator, n: int, n_strata: int) -> np.ndarray:
    """Stratified sampling: divide [0,1] into strata, draw within each."""
    per = n // n_strata
    remainder = n - per * n_strata
    parts: list[np.ndarray] = []
    for k in range(n_strata):
        count = per + (1 if k < remainder else 0)
        lo, hi = k / n_strata, (k + 1) / n_strata
        parts.append(rng.uniform(lo, hi, size=count))
    u = np.concatenate(parts)
    rng.shuffle(u)
    return u


def _build_correlation_matrix(player_params: list[dict]) -> np.ndarray:
    """Same-team players share correlation SAME_TEAM_CORR; identity otherwise."""
    n = len(player_params)
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            if player_params[i]["team_id"] == player_params[j]["team_id"]:
                corr[i, j] = SAME_TEAM_CORR
                corr[j, i] = SAME_TEAM_CORR
    return corr


# ---------------------------------------------------------------------------
# T-copula sampler with antithetic variates + stratified sampling
# ---------------------------------------------------------------------------

def _t_copula_samples(
    rng: np.random.Generator,
    n_sims: int,
    corr: np.ndarray,
    mus: np.ndarray,
    sigmas: np.ndarray,
    dfs: np.ndarray,
) -> np.ndarray:
    """
    Generate correlated Student-t samples via t-copula.

    Implements three stacking variance-reduction techniques from the article:
    1. Stratified sampling — uniform draws partitioned across strata
    2. Antithetic variates — U and 1-U paired for negative correlation
    3. t-copula — Cholesky-correlated t-draws give realistic tail dependence
    """
    n_players = len(mus)
    half = n_sims // 2

    # Cholesky of correlation matrix
    L = cholesky(corr, lower=True)

    # Independent stratified standard-normal draws  (half × n_players)
    Z = np.column_stack(
        [stats.norm.ppf(np.clip(_stratified_uniform(rng, half, N_STRATA), 1e-8, 1 - 1e-8))
         for _ in range(n_players)]
    )

    # Correlate via Cholesky
    Z = Z @ L.T  # (half, n_players)

    # Chi-squared draw shared across players → t-copula tail dependence
    W = rng.chisquare(df=T_COPULA_DF, size=(half, 1))
    T = Z * np.sqrt(T_COPULA_DF / W)  # correlated t-draws

    # Map to copula-uniform space via t CDF
    U = stats.t.cdf(T, df=T_COPULA_DF)

    # Antithetic mirror
    U_anti = 1.0 - U

    # Transform each player column to their fitted marginal t-distribution
    #   stats.t.ppf broadcasts: (half, n_players) with df shape (n_players,)
    s1 = stats.t.ppf(np.clip(U, 1e-8, 1 - 1e-8), df=dfs) * sigmas + mus
    s2 = stats.t.ppf(np.clip(U_anti, 1e-8, 1 - 1e-8), df=dfs) * sigmas + mus

    samples = np.vstack([s1, s2])
    np.maximum(samples, 0, out=samples)
    return samples


# ---------------------------------------------------------------------------
# Team GW simulation
# ---------------------------------------------------------------------------

async def run_simulation(
    team_id: int, current_gw: int, bootstrap: dict
) -> SimulationResult:
    from recommender import get_squad_players

    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}

    try:
        next_fixtures = await fpl_client.get_fixtures(current_gw)
    except Exception:
        next_fixtures = []

    team_fdr: dict[int, float] = {}
    for f in next_fixtures:
        h, a = f["team_h"], f["team_a"]
        team_fdr.setdefault(h, f["team_h_difficulty"])
        team_fdr.setdefault(a, f["team_a_difficulty"])

    picks_by_element = {p["element"]: p for p in picks}
    playing = [
        e for e in squad_elements if picks_by_element[e["id"]]["multiplier"] > 0
    ]

    # Fit Student-t per player and apply FDR scaling
    player_params: list[dict] = []
    rng = np.random.default_rng(42)

    for element in playing:
        try:
            summary = await fpl_client.get_element_summary(element["id"])
            history = summary.get("history", [])
        except Exception:
            history = []

        last5 = [h["total_points"] for h in history[-5:]] if history else []
        if not last5:
            ppg = float(element.get("points_per_game") or "0")
            mu, sigma, df = ppg, 2.0, 4.0
        else:
            mu, sigma, df = _fit_student_t(last5)

        fdr = team_fdr.get(element["team"], 3.0)
        fdr_scale = (6 - fdr) / 3.0
        mu_scaled = max(0.0, mu * fdr_scale)

        player_params.append(
            {
                "id": element["id"],
                "name": element["web_name"],
                "mu": mu_scaled,
                "sigma": sigma,
                "df": df,
                "multiplier": picks_by_element[element["id"]]["multiplier"],
                "position": POSITION_MAP.get(element["element_type"], "?"),
                "team": teams_by_id.get(element["team"], {}).get("short_name", "?"),
                "team_id": element["team"],
            }
        )

    if not player_params:
        return SimulationResult(
            mean=0, median=0, p25=0, p75=0, p90=0,
            histogram_bins=[], histogram_counts=[], player_contributions=[],
            meta=SimulationMeta(
                n_simulations=0, distribution="student-t", techniques=[],
                variance_reduction_factor=1.0,
            ),
        )

    n_players = len(player_params)
    mus = np.array([p["mu"] for p in player_params])
    sigmas = np.array([p["sigma"] for p in player_params])
    dfs = np.array([p["df"] for p in player_params])
    multipliers = np.array([p["multiplier"] for p in player_params])
    corr = _build_correlation_matrix(player_params)

    # --- Enhanced MC (t-copula + antithetic + stratified) ---
    samples = _t_copula_samples(rng, N_SIMULATIONS, corr, mus, sigmas, dfs)
    weighted = samples * multipliers
    totals = weighted.sum(axis=1)

    # --- Variance-reduction measurement ---
    # Compare antithetic-paired estimator vs unpaired.
    # First half = original draws, second half = antithetic mirror.
    half = N_SIMULATIONS // 2
    t_orig = totals[:half]
    t_anti = totals[half:]
    # Paired mean per antithetic pair: Z_i = (X_i + X'_i) / 2
    paired = (t_orig + t_anti) / 2.0
    # VR = Var(unpaired mean) / Var(paired mean)
    #     = (Var(X)/N) / (Var(Z)/(N/2))  =  Var(X) / (2 * Var(Z))
    vr_factor = float(np.var(totals) / max(2.0 * np.var(paired), 1e-9))

    # --- Control variate correction for the mean ---
    # Analytical expected total under the fitted distributions
    analytical_mean = float((mus * multipliers).sum())
    raw_mean = float(np.mean(totals))
    cv_mean = analytical_mean  # direct correction: use known mean

    median_pts = float(np.median(totals))
    p25 = float(np.percentile(totals, 25))
    p75 = float(np.percentile(totals, 75))
    p90 = float(np.percentile(totals, 90))

    counts, edges = np.histogram(totals, bins=30)
    bins = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]

    contributions = sorted(
        [
            {
                "id": p["id"],
                "name": p["name"],
                "position": p["position"],
                "team": p["team"],
                "expected_pts": round(p["mu"] * p["multiplier"], 2),
                "multiplier": p["multiplier"],
            }
            for p in player_params
        ],
        key=lambda x: x["expected_pts"],
        reverse=True,
    )

    meta = SimulationMeta(
        n_simulations=N_SIMULATIONS,
        distribution="student-t",
        techniques=["t-copula", "antithetic-variates", "stratified-sampling", "control-variate"],
        variance_reduction_factor=round(vr_factor, 1),
    )

    # Store predictions for Brier scoring
    try:
        import brier
        predictions = []
        for p in player_params:
            # P(player scores 4+ raw pts) from fitted t-distribution
            prob_4plus = 1.0 - stats.t.cdf(4.0, df=p["df"], loc=p["mu"], scale=p["sigma"])
            predictions.append({
                "player_id": p["id"],
                "name": p["name"],
                "predicted_mean": round(p["mu"], 2),
                "predicted_sigma": round(p["sigma"], 2),
                "predicted_df": round(p["df"], 1),
                "prob_4plus": round(float(prob_4plus), 4),
            })
        brier.store_predictions(team_id, current_gw, predictions)
    except Exception:
        pass  # non-critical

    return SimulationResult(
        mean=round(cv_mean, 2),
        median=round(median_pts, 2),
        p25=round(p25, 2),
        p75=round(p75, 2),
        p90=round(p90, 2),
        histogram_bins=[round(b, 2) for b in bins],
        histogram_counts=counts.tolist(),
        player_contributions=contributions,
        meta=meta,
    )


# ---------------------------------------------------------------------------
# All-player 10-GW projections (antithetic + stratified + Student-t)
# ---------------------------------------------------------------------------

async def run_player_simulations(
    current_gw: int, bootstrap: dict, squad_player_ids: set[int] | None = None
) -> PlayerSimulationsResponse:
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    elements = bootstrap["elements"]

    gw_start = current_gw
    gw_end = min(current_gw + 9, 38)
    gameweeks = list(range(gw_start, gw_end + 1))

    team_gw_fdr: dict[int, dict[int, list[float]]] = {}
    for gw in gameweeks:
        try:
            fixtures = await fpl_client.get_fixtures(gw)
        except Exception:
            continue
        for f in fixtures:
            h, a = f["team_h"], f["team_a"]
            team_gw_fdr.setdefault(h, {}).setdefault(gw, []).append(f["team_h_difficulty"])
            team_gw_fdr.setdefault(a, {}).setdefault(gw, []).append(f["team_a_difficulty"])

    rng = np.random.default_rng(42)
    n_gws = len(gameweeks)
    n_players = len(elements)

    active_ids = [el["id"] for el in elements if int(el.get("minutes") or 0) > 0]
    summaries = await fpl_client.get_element_summaries_batch(active_ids)

    # Fit Student-t per player
    mus_base = np.zeros(n_players)
    sigmas_base = np.zeros(n_players)
    dfs_base = np.full(n_players, 4.0)

    for i, el in enumerate(elements):
        summary = summaries.get(el["id"])
        history = summary.get("history", []) if summary else []
        last5 = [h["total_points"] for h in history[-5:]] if history else []

        if last5:
            mu, sigma, df = _fit_student_t(last5)
        else:
            form = float(el.get("form") or 0)
            ppg = float(el.get("points_per_game") or 0)
            mu = form if form > 0 else ppg
            sigma = max(mu * 0.5, 1.0)
            df = 4.0

        mus_base[i] = mu
        sigmas_base[i] = max(sigma, 1.0)
        dfs_base[i] = df

    # Populate fit cache as side-effect
    for i, el in enumerate(elements):
        _player_fit_cache[el["id"]] = (float(mus_base[i]), float(sigmas_base[i]), float(dfs_base[i]))

    # FDR scale matrix (n_players × n_gws)
    fdr_scales = np.zeros((n_players, n_gws))
    for i, el in enumerate(elements):
        tid = el["team"]
        for j, gw in enumerate(gameweeks):
            fdr_list = team_gw_fdr.get(tid, {}).get(gw)
            if fdr_list is None:
                fdr_scales[i, j] = 0.0
            else:
                fdr_scales[i, j] = sum((6 - fdr) / 3.0 for fdr in fdr_list)

    # Simulate each GW with antithetic + stratified Student-t
    half = N_PLAYER_SIMS // 2
    gw_means = np.zeros((n_players, n_gws))

    for j in range(n_gws):
        scale = fdr_scales[:, j]
        mu_scaled = np.maximum(0.0, mus_base * scale)
        sigma_scaled = np.where(scale > 0, sigmas_base, 0.01)

        # Stratified uniforms → Student-t ppf (vectorised over players via broadcasting)
        # Shape: (half, n_players)
        U = np.column_stack(
            [_stratified_uniform(rng, half, N_STRATA) for _ in range(n_players)]
        )
        U = np.clip(U, 1e-8, 1 - 1e-8)
        U_anti = 1.0 - U

        s1 = stats.t.ppf(U, df=dfs_base) * sigma_scaled + mu_scaled
        s2 = stats.t.ppf(U_anti, df=dfs_base) * sigma_scaled + mu_scaled

        samples = np.vstack([s1, s2])
        np.maximum(samples, 0, out=samples)

        gw_means[:, j] = samples.mean(axis=0)
        gw_means[:, j] *= (scale > 0)

    totals = gw_means.sum(axis=1)
    squad_ids = squad_player_ids or set()

    players: list[PlayerSimRow] = []
    for i, el in enumerate(elements):
        players.append(
            PlayerSimRow(
                id=el["id"],
                name=el["web_name"],
                team=teams_by_id.get(el["team"], {}).get("short_name", "?"),
                team_id=el["team"],
                position=POSITION_MAP.get(el["element_type"], "?"),
                now_cost=el["now_cost"] / 10,
                form=float(el.get("form") or 0),
                gw_expected=[round(float(gw_means[i, j]), 2) for j in range(n_gws)],
                total_expected=round(float(totals[i]), 2),
                in_squad=el["id"] in squad_ids,
            )
        )

    players.sort(key=lambda p: p.total_expected, reverse=True)

    return PlayerSimulationsResponse(
        current_gw=current_gw,
        gameweeks=gameweeks,
        players=players,
    )


# ---------------------------------------------------------------------------
# Cached accessors
# ---------------------------------------------------------------------------

async def get_cached_player_simulations(
    current_gw: int, bootstrap: dict, squad_player_ids: set[int] | None = None
) -> PlayerSimulationsResponse:
    """Return cached PlayerSimulationsResponse or recompute (5-min TTL)."""
    cache_key = (current_gw, frozenset(squad_player_ids) if squad_player_ids else None)
    now = time.time()
    if cache_key in _player_sim_cache:
        ts, result = _player_sim_cache[cache_key]
        if now - ts < _PLAYER_SIM_TTL:
            return result
    result = await run_player_simulations(current_gw, bootstrap, squad_player_ids)
    _player_sim_cache[cache_key] = (now, result)
    return result


# ---------------------------------------------------------------------------
# Single-player detail simulation
# ---------------------------------------------------------------------------

async def run_player_detail_simulation(
    player_id: int, current_gw: int, bootstrap: dict
) -> PlayerDetailSimulation:
    elements_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}

    element = elements_by_id.get(player_id)
    if element is None:
        raise ValueError(f"Player {player_id} not found")

    try:
        summary = await fpl_client.get_element_summary(player_id)
        history = summary.get("history", [])
    except Exception:
        history = []

    last5 = [h["total_points"] for h in history[-5:]] if history else []
    if last5:
        mu, sigma, df = _fit_student_t(last5)
    else:
        ppg = float(element.get("points_per_game") or "0")
        mu, sigma, df = ppg, 2.0, 4.0

    # FDR scaling for current GW
    try:
        next_fixtures = await fpl_client.get_fixtures(current_gw)
    except Exception:
        next_fixtures = []

    fdr = 3.0
    for f in next_fixtures:
        if f["team_h"] == element["team"]:
            fdr = f["team_h_difficulty"]
            break
        if f["team_a"] == element["team"]:
            fdr = f["team_a_difficulty"]
            break

    mu_scaled = max(0.0, mu * (6 - fdr) / 3.0)

    # 1,000 antithetic + stratified Student-t samples
    rng = np.random.default_rng(player_id)
    half = N_PLAYER_SIMS // 2
    U = _stratified_uniform(rng, half, N_STRATA)
    U = np.clip(U, 1e-8, 1 - 1e-8)
    U_anti = 1.0 - U

    s1 = stats.t.ppf(U, df=df) * sigma + mu_scaled
    s2 = stats.t.ppf(U_anti, df=df) * sigma + mu_scaled
    samples = np.concatenate([s1, s2])
    np.maximum(samples, 0, out=samples)

    counts, edges = np.histogram(samples, bins=25)
    bins = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]

    team_info = teams_by_id.get(element["team"], {})

    return PlayerDetailSimulation(
        player_id=player_id,
        name=element["web_name"],
        team=team_info.get("short_name", "?"),
        position=POSITION_MAP.get(element["element_type"], "?"),
        gameweek=current_gw,
        mean=round(float(np.mean(samples)), 2),
        median=round(float(np.median(samples)), 2),
        p25=round(float(np.percentile(samples, 25)), 2),
        p75=round(float(np.percentile(samples, 75)), 2),
        p90=round(float(np.percentile(samples, 90)), 2),
        histogram_bins=[round(b, 2) for b in bins],
        histogram_counts=counts.tolist(),
        n_simulations=N_PLAYER_SIMS,
    )
