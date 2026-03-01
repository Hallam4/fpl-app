import numpy as np
import fpl_client
from models import SimulationResult, PlayerSimRow, PlayerSimulationsResponse

N_SIMULATIONS = 10_000
N_PLAYER_SIMS = 1_000
POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


async def run_simulation(
    team_id: int, current_gw: int, bootstrap: dict
) -> SimulationResult:
    from recommender import get_squad_players

    squad_elements, picks, bank, players_by_id = await get_squad_players(
        team_id, current_gw, bootstrap
    )
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}

    # Fetch next GW fixtures for FDR scaling
    try:
        next_fixtures = await fpl_client.get_fixtures(current_gw)
    except Exception:
        next_fixtures = []

    team_fdr: dict[int, float] = {}
    for f in next_fixtures:
        h, a = f["team_h"], f["team_a"]
        if h not in team_fdr:
            team_fdr[h] = f["team_h_difficulty"]
        if a not in team_fdr:
            team_fdr[a] = f["team_a_difficulty"]

    # Build playing XI (multiplier > 0 in picks)
    picks_by_element = {p["element"]: p for p in picks}
    playing = [
        e for e in squad_elements
        if picks_by_element[e["id"]]["multiplier"] > 0
    ]

    # Fetch last-5 GW history for each player and fit Gaussian
    player_params: list[dict] = []
    rng = np.random.default_rng(42)

    for element in playing:
        try:
            summary = await fpl_client.get_element_summary(element["id"])
            history = summary.get("history", [])
        except Exception:
            history = []

        last5_pts = [h["total_points"] for h in history[-5:]] if history else []
        if not last5_pts:
            # Fallback: use season average
            pts_per_game = element.get("points_per_game") or "0"
            mu = float(pts_per_game)
            sigma = 2.0
        else:
            mu = float(np.mean(last5_pts))
            sigma = float(np.std(last5_pts)) if len(last5_pts) > 1 else 2.0

        # Scale by FDR (harder fixture → lower expected points)
        fdr = team_fdr.get(element["team"], 3.0)
        fdr_scale = (6 - fdr) / 3.0  # FDR 1 → 1.67, FDR 5 → 0.33
        mu_scaled = max(0.0, mu * fdr_scale)
        sigma_scaled = max(0.5, sigma)

        multiplier = picks_by_element[element["id"]]["multiplier"]

        player_params.append(
            {
                "id": element["id"],
                "name": element["web_name"],
                "mu": mu_scaled,
                "sigma": sigma_scaled,
                "multiplier": multiplier,
                "position": POSITION_MAP.get(element["element_type"], "?"),
                "team": teams_by_id.get(element["team"], {}).get("short_name", "?"),
            }
        )

    if not player_params:
        return SimulationResult(
            mean=0, median=0, p25=0, p75=0, p90=0,
            histogram_bins=[], histogram_counts=[], player_contributions=[]
        )

    # Run Monte Carlo
    n_players = len(player_params)
    mus = np.array([p["mu"] for p in player_params])
    sigmas = np.array([p["sigma"] for p in player_params])
    multipliers = np.array([p["multiplier"] for p in player_params])

    # Shape: (N_SIMULATIONS, n_players)
    samples = rng.normal(loc=mus, scale=sigmas, size=(N_SIMULATIONS, n_players))
    samples = np.maximum(samples, 0)  # floor at 0

    weighted = samples * multipliers  # captain counts double
    totals = weighted.sum(axis=1)

    mean_pts = float(np.mean(totals))
    median_pts = float(np.median(totals))
    p25 = float(np.percentile(totals, 25))
    p75 = float(np.percentile(totals, 75))
    p90 = float(np.percentile(totals, 90))

    # Histogram
    counts, bin_edges = np.histogram(totals, bins=30)
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(counts))]

    # Per-player expected contributions
    player_contributions = [
        {
            "id": p["id"],
            "name": p["name"],
            "position": p["position"],
            "team": p["team"],
            "expected_pts": round(p["mu"] * p["multiplier"], 2),
            "multiplier": p["multiplier"],
        }
        for p in player_params
    ]
    player_contributions.sort(key=lambda x: x["expected_pts"], reverse=True)

    return SimulationResult(
        mean=round(mean_pts, 2),
        median=round(median_pts, 2),
        p25=round(p25, 2),
        p75=round(p75, 2),
        p90=round(p90, 2),
        histogram_bins=[round(b, 2) for b in bin_centers],
        histogram_counts=counts.tolist(),
        player_contributions=player_contributions,
    )


async def run_player_simulations(
    current_gw: int, bootstrap: dict, squad_player_ids: set[int] | None = None
) -> PlayerSimulationsResponse:
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}
    elements = bootstrap["elements"]

    # Determine GW range (up to 10 GWs, capped at 38)
    gw_start = current_gw
    gw_end = min(current_gw + 9, 38)
    gameweeks = list(range(gw_start, gw_end + 1))

    # Fetch fixtures for all target GWs and build team → gw → [fdr] map
    team_gw_fdr: dict[int, dict[int, list[float]]] = {}
    for gw in gameweeks:
        try:
            fixtures = await fpl_client.get_fixtures(gw)
        except Exception:
            continue
        for f in fixtures:
            h, a = f["team_h"], f["team_a"]
            team_gw_fdr.setdefault(h, {}).setdefault(gw, []).append(
                f["team_h_difficulty"]
            )
            team_gw_fdr.setdefault(a, {}).setdefault(gw, []).append(
                f["team_a_difficulty"]
            )

    rng = np.random.default_rng(42)
    n_gws = len(gameweeks)
    n_players = len(elements)

    # Build per-player base mu/sigma from bootstrap data (no individual API calls)
    mus_base = np.zeros(n_players)
    sigmas_base = np.zeros(n_players)
    for i, el in enumerate(elements):
        form = float(el.get("form") or 0)
        ppg = float(el.get("points_per_game") or 0)
        mu = form if form > 0 else ppg
        mus_base[i] = mu
        sigmas_base[i] = max(mu * 0.5, 1.0)

    # Build FDR scale matrix: (n_players, n_gws)
    fdr_scales = np.zeros((n_players, n_gws))
    for i, el in enumerate(elements):
        tid = el["team"]
        for j, gw in enumerate(gameweeks):
            fdr_list = team_gw_fdr.get(tid, {}).get(gw)
            if fdr_list is None:
                # BGW — no fixture
                fdr_scales[i, j] = 0.0
            else:
                # Sum FDR scales for DGW (multiple fixtures)
                fdr_scales[i, j] = sum((6 - fdr) / 3.0 for fdr in fdr_list)

    # Vectorized Monte Carlo: simulate each GW
    # gw_means shape: (n_players, n_gws)
    gw_means = np.zeros((n_players, n_gws))
    for j in range(n_gws):
        scale = fdr_scales[:, j]  # (n_players,)
        mu_scaled = np.maximum(0.0, mus_base * scale)
        # For BGW players (scale==0), sigma should be 0 too
        sigma_scaled = np.where(scale > 0, sigmas_base, 0.0)
        # (N_PLAYER_SIMS, n_players)
        samples = rng.normal(
            loc=mu_scaled, scale=np.maximum(sigma_scaled, 0.01),
            size=(N_PLAYER_SIMS, n_players)
        )
        samples = np.maximum(samples, 0)
        gw_means[:, j] = samples.mean(axis=0)
        # Zero out BGW players
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
