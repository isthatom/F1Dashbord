"""
F1 Dashboard preview: visualize data/f1.db without opening Power BI.

Run with: streamlit run app.py
"""

import sqlite3

import altair as alt
import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:
    raise SystemExit(
        "streamlit is not installed.\n"
        "  Activate the project venv and install dev deps, then run:\n"
        "      .venv\\Scripts\\activate\n"
        '      pip install -e ".[dev]"\n'
        "      streamlit run app.py"
    ) from None

from config import settings

st.set_page_config(page_title="F1 Data Preview", layout="wide")

TEAM_COLORS: dict[str, str] = {
    "Red Bull Racing": "#3671C6",
    "Scuderia Ferrari": "#E8002D",
    "Mercedes Formula 1 Team": "#27F4D2",
    "McLaren Formula 1 Team": "#FF8000",
    "Aston Martin F1 Team": "#229971",
    "Alpine F1 Team": "#0093CC",
    "Haas F1 Team": "#B6BABD",
    "RB F1 Team": "#6692FF",
    "Williams Racing": "#64C4FF",
    "Sauber F1 Team": "#52E252",
    "Audi Revolut F1 Team": "#8B0000",
    "Cadillac Formula 1 Team": "#0057B8",
    "Alfa Romeo": "#900000",
    "AlphaTauri": "#2B4562",
    "Toro Rosso": "#469BFF",
    "Racing Point": "#F596C8",
    "Force India": "#F596C8",
    "Renault": "#FFF500",
}

WIN = "#2e9e5b"
LOSS = "#d62728"


def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        with sqlite3.connect(settings.DB_PATH) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return pd.DataFrame()


def team_scale() -> alt.Scale:
    return alt.Scale(domain=list(TEAM_COLORS), range=list(TEAM_COLORS.values()))


@st.cache_data(ttl=300)
def load_seasons() -> list[int]:
    df = _query("SELECT DISTINCT season FROM races ORDER BY season DESC")
    if df.empty or "season" not in df.columns:
        return []
    return df["season"].astype(int).tolist()


@st.cache_data(ttl=300)
def load_meta() -> pd.DataFrame:
    return _query("SELECT key, value FROM pipeline_meta ORDER BY key")


@st.cache_data(ttl=300)
def load_driver_standings(season: int) -> pd.DataFrame:
    return _query(
        """
        SELECT ds.position, ds.driver_id, d.full_name, t.team_name, ds.points, ds.wins
        FROM driver_standings ds
        LEFT JOIN drivers d ON d.driver_id = ds.driver_id
        LEFT JOIN teams t ON t.team_id = ds.team_id
        WHERE ds.season = ?
        ORDER BY ds.position
        """,
        (season,),
    )


@st.cache_data(ttl=300)
def load_constructor_standings(season: int) -> pd.DataFrame:
    return _query(
        """
        SELECT position, team_name, points, wins
        FROM constructor_standings
        WHERE season = ?
        ORDER BY position
        """,
        (season,),
    )


@st.cache_data(ttl=300)
def load_podium_counts(season: int) -> pd.DataFrame:
    return _query(
        """
        SELECT rr.driver_id, d.full_name, t.team_name,
               SUM(CASE WHEN rr.position = 1 THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END) AS podiums,
               COUNT(*) AS races
        FROM race_results rr
        LEFT JOIN drivers d ON d.driver_id = rr.driver_id
        LEFT JOIN teams t ON t.team_id = rr.team_id
        WHERE rr.season = ?
        GROUP BY rr.driver_id
        ORDER BY wins DESC, podiums DESC, full_name
        """,
        (season,),
    )


@st.cache_data(ttl=300)
def load_points_trend(season: int, driver_ids: tuple[str, ...]) -> pd.DataFrame:
    if not driver_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in driver_ids)
    return _query(
        f"""
        SELECT pt.round, pt.driver_id, d.full_name, t.team_name,
               pt.race_points, pt.cumulative_points, pt.season_avg_points_per_race
        FROM analytics_points_trend pt
        LEFT JOIN driver_standings ds ON ds.season = pt.season AND ds.driver_id = pt.driver_id
        LEFT JOIN teams t ON t.team_id = ds.team_id
        LEFT JOIN drivers d ON d.driver_id = pt.driver_id
        WHERE pt.season = ? AND pt.driver_id IN ({placeholders})
        ORDER BY pt.round
        """,
        (season, *driver_ids),
    )


@st.cache_data(ttl=300)
def load_position_matrix(season: int, driver_ids: tuple[str, ...]) -> pd.DataFrame:
    if not driver_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in driver_ids)
    return _query(
        f"""
        SELECT rr.round, rr.driver_id, d.full_name, t.team_name, rr.position, rr.points
        FROM race_results rr
        LEFT JOIN drivers d ON d.driver_id = rr.driver_id
        LEFT JOIN teams t ON t.team_id = rr.team_id
        WHERE rr.season = ? AND rr.driver_id IN ({placeholders})
        ORDER BY rr.round, rr.position
        """,
        (season, *driver_ids),
    )


@st.cache_data(ttl=300)
def load_rolling_position(season: int, driver_ids: tuple[str, ...]) -> pd.DataFrame:
    if not driver_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in driver_ids)
    return _query(
        f"""
        SELECT rp.round, rp.driver_id, d.full_name, t.team_name, rp.rolling_avg_position
        FROM analytics_rolling_position rp
        LEFT JOIN driver_standings ds ON ds.season = rp.season AND ds.driver_id = rp.driver_id
        LEFT JOIN teams t ON t.team_id = ds.team_id
        LEFT JOIN drivers d ON d.driver_id = rp.driver_id
        WHERE rp.season = ? AND rp.driver_id IN ({placeholders})
        ORDER BY rp.round
        """,
        (season, *driver_ids),
    )


@st.cache_data(ttl=300)
def load_recent_form(season: int, driver_ids: tuple[str, ...]) -> pd.DataFrame:
    if not driver_ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in driver_ids)
    return _query(
        f"""
        SELECT rf.round, rf.driver_id, d.full_name, t.team_name, rf.recent_form_points
        FROM analytics_recent_form rf
        LEFT JOIN driver_standings ds ON ds.season = rf.season AND ds.driver_id = rf.driver_id
        LEFT JOIN teams t ON t.team_id = ds.team_id
        LEFT JOIN drivers d ON d.driver_id = rf.driver_id
        WHERE rf.season = ? AND rf.driver_id IN ({placeholders})
        ORDER BY rf.round
        """,
        (season, *driver_ids),
    )


@st.cache_data(ttl=300)
def load_teammate_h2h(season: int) -> pd.DataFrame:
    return _query(
        """
        SELECT tc.round, tc.team_id, t.team_name, tc.driver_id, d.full_name,
               tc.driver_points, tc.teammate_points, tc.points_advantage, tc.position_advantage
        FROM analytics_teammate_comparison tc
        LEFT JOIN teams t ON t.team_id = tc.team_id
        LEFT JOIN drivers d ON d.driver_id = tc.driver_id
        WHERE tc.season = ?
        ORDER BY tc.round, t.team_name
        """,
        (season,),
    )


@st.cache_data(ttl=300)
def load_h2h_summary(season: int) -> pd.DataFrame:
    return _query(
        """
        SELECT tc.team_id, t.team_name, tc.driver_id, d.full_name AS driver_name,
               SUM(tc.driver_points) AS total_points,
               SUM(CASE WHEN tc.driver_points > tc.teammate_points THEN 1 ELSE 0 END) AS h2h_wins,
               COUNT(*) AS rounds
        FROM analytics_teammate_comparison tc
        LEFT JOIN teams t ON t.team_id = tc.team_id
        LEFT JOIN drivers d ON d.driver_id = tc.driver_id
        WHERE tc.season = ?
        GROUP BY tc.team_id, tc.driver_id
        ORDER BY t.team_name, total_points DESC
        """,
        (season,),
    )


@st.cache_data(ttl=300)
def load_rounds(season: int) -> pd.DataFrame:
    return _query(
        """
        SELECT round, race_name, race_date
        FROM races
        WHERE season = ?
        ORDER BY round
        """,
        (season,),
    )


@st.cache_data(ttl=300)
def load_race_results(season: int, round_no: int) -> pd.DataFrame:
    df = _query(
        """
        SELECT rr.driver_id, d.full_name, t.team_name, rr.position, rr.grid,
               rr.finished, rr.points, rr.retired, rr.time
        FROM race_results rr
        LEFT JOIN drivers d ON d.driver_id = rr.driver_id
        LEFT JOIN teams t ON t.team_id = rr.team_id
        WHERE rr.season = ? AND rr.round = ?
        ORDER BY CASE WHEN rr.position IS NULL THEN 1 ELSE 0 END, rr.position
        """,
        (season, round_no),
    )
    if not df.empty and "grid" in df.columns:
        df["grid"] = pd.to_numeric(df["grid"], errors="coerce")
    return df


def _freshness(meta: pd.DataFrame) -> str:
    if meta.empty:
        return "unknown (no pipeline_meta table)"
    values = dict(zip(meta["key"], meta["value"], strict=False))
    finished = values.get("finished_at")
    if not finished:
        return "unknown"
    return finished.strip('"').replace("T", " ")[:19] + " UTC"


def _download(df: pd.DataFrame, label: str) -> None:
    st.download_button(
        f"Download {label} CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"{label.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )


def _team_line_chart(df: pd.DataFrame, y: str, title: str, height: int = 320) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("round:Q", title="Round", scale=alt.Scale(zero=False)),
            y=alt.Y(y + ":Q", title=title),
            color=alt.Color("team_name:N", scale=team_scale(), legend=None),
            strokeDash=alt.StrokeDash("full_name:N", legend=None),
            tooltip=[
                "full_name",
                "team_name",
                "round",
                alt.Tooltip(y, format=".1f"),
            ],
        )
        .properties(height=height)
        .interactive()
    )


def _render_season_hub(season: int) -> None:
    ds = load_driver_standings(season)
    cs = load_constructor_standings(season)
    pods = load_podium_counts(season)
    if ds.empty and cs.empty:
        st.warning("No standings for this season.")
        return

    leader = ds.iloc[0]
    gap = leader["points"] - ds.iloc[1]["points"] if len(ds) > 1 else 0.0
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Championship leader", f"{leader['full_name']} · {leader['points']:.0f} pts")
    m2.metric("Gap to 2nd", f"{gap:.0f} pts")
    if not pods.empty:
        top_win = pods.iloc[0]
        top_pod = pods.sort_values("podiums", ascending=False).iloc[0]
        m3.metric("Most wins", f"{top_win['full_name']} ({top_win['wins']})")
        m4.metric("Most podiums", f"{top_pod['full_name']} ({top_pod['podiums']})")
    else:
        m3.metric("Most wins", "-")
        m4.metric("Most podiums", "-")
    if not cs.empty:
        c_leader = cs.iloc[0]
        m5.metric("Constructor leader", f"{c_leader['team_name']} · {c_leader['points']:.0f} pts")
    else:
        m5.metric("Constructor leader", "-")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Driver standings")
        if not ds.empty:
            chart = (
                alt.Chart(ds)
                .mark_bar()
                .encode(
                    x=alt.X("full_name:N", title=None, sort="-y"),
                    y=alt.Y("points:Q", title="Points"),
                    color=alt.Color("team_name:N", scale=team_scale(), legend=None),
                    tooltip=["full_name", "team_name", "points", "wins"],
                )
                .properties(height=340)
            )
            st.altair_chart(chart, width="stretch")
            st.dataframe(
                ds,
                hide_index=True,
                width="stretch",
                column_config={
                    "position": st.column_config.NumberColumn("Pos", format="%d"),
                    "full_name": "Driver",
                    "team_name": "Team",
                    "points": st.column_config.NumberColumn("Points", format="%.1f"),
                    "wins": "Wins",
                },
            )
            _download(ds, "Driver standings")
    with col2:
        st.subheader("Constructor standings")
        if not cs.empty:
            chart = (
                alt.Chart(cs)
                .mark_bar()
                .encode(
                    x=alt.X("team_name:N", title=None, sort="-y"),
                    y=alt.Y("points:Q", title="Points"),
                    color=alt.Color("team_name:N", scale=team_scale(), legend=None),
                    tooltip=["team_name", "points", "wins"],
                )
                .properties(height=340)
            )
            st.altair_chart(chart, width="stretch")
            st.dataframe(
                cs,
                hide_index=True,
                width="stretch",
                column_config={
                    "position": st.column_config.NumberColumn("Pos", format="%d"),
                    "team_name": "Team",
                    "points": st.column_config.NumberColumn("Points", format="%.1f"),
                    "wins": "Wins",
                },
            )
            _download(cs, "Constructor standings")


def _render_points_trend(season: int, picked: list[str]) -> None:
    trend = load_points_trend(season, tuple(picked))
    if trend.empty:
        st.info("Pick at least one driver.")
        return
    metric = st.radio("Measure", ["Cumulative points", "Avg points per race"], horizontal=True)
    y = "cumulative_points" if metric == "Cumulative points" else "season_avg_points_per_race"
    title = "Points" if metric == "Cumulative points" else "Avg points per race"
    st.altair_chart(_team_line_chart(trend, y, title), width="stretch")
    _download(trend, "Points trend")


def _render_race_positions(season: int, picked: list[str]) -> None:
    mat = load_position_matrix(season, tuple(picked))
    if mat.empty:
        st.info("Pick at least one driver.")
        return
    mat = mat[mat["position"].notna()]
    heat = (
        alt.Chart(mat)
        .mark_rect()
        .encode(
            x=alt.X("round:O", title="Round"),
            y=alt.Y(
                "full_name:N",
                title=None,
                sort=alt.EncodingSortField(field="points", op="sum", order="descending"),
            ),
            color=alt.Color(
                "position:Q",
                title="Finish",
                scale=alt.Scale(scheme="redyellowgreen", domain=[1, 20]),
            ),
            tooltip=["full_name", "team_name", "round", "position", "points"],
        )
        .properties(height=520)
    )
    st.subheader("Finish position by round")
    st.altair_chart(heat, width="stretch")
    _download(mat, "Position matrix")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Rolling avg position (lower = better)")
        roll = load_rolling_position(season, tuple(picked))
        if roll.empty:
            st.info("No rolling position data.")
        else:
            chart = (
                alt.Chart(roll)
                .mark_line(point=True)
                .encode(
                    x=alt.X("round:Q", title="Round", scale=alt.Scale(zero=False)),
                    y=alt.Y(
                        "rolling_avg_position:Q",
                        title="Avg position",
                        scale=alt.Scale(reverse=True),
                    ),
                    color=alt.Color("team_name:N", scale=team_scale(), legend=None),
                    strokeDash=alt.StrokeDash("full_name:N", legend=None),
                    tooltip=["full_name", "team_name", "round", "rolling_avg_position"],
                )
                .properties(height=300)
                .interactive()
            )
            st.altair_chart(chart, width="stretch")
            _download(roll, "Rolling position")
    with col2:
        st.subheader("Recent form (points, last 3 races)")
        form = load_recent_form(season, tuple(picked))
        if form.empty:
            st.info("No recent form data.")
        else:
            chart = (
                alt.Chart(form)
                .mark_bar(opacity=0.7)
                .encode(
                    x=alt.X("round:Q", title="Round"),
                    y=alt.Y("recent_form_points:Q", title="Points"),
                    color=alt.Color("team_name:N", scale=team_scale(), legend=None),
                    tooltip=["full_name", "team_name", "round", "recent_form_points"],
                )
                .properties(height=300)
                .interactive()
            )
            st.altair_chart(chart, width="stretch")
            _download(form, "Recent form")


def _render_teammate_h2h(season: int) -> None:
    h2h = load_teammate_h2h(season)
    summary = load_h2h_summary(season)
    if h2h.empty or summary.empty:
        st.info("No teammate comparisons for this season.")
        return

    teams = list(summary["team_name"].dropna().unique())
    team = st.selectbox("Team", teams, key="h2h_team")
    pair = summary[summary["team_name"] == team].reset_index(drop=True)
    if len(pair) < 2:
        st.warning("Team needs two drivers.")
        return
    d_a, d_b = pair.iloc[0], pair.iloc[1]
    wins_a, wins_b = int(d_a["h2h_wins"]), int(d_b["h2h_wins"])
    draws = max(0, int(d_a["rounds"] - wins_a - wins_b))
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{d_a['driver_name']} (wins)", f"{wins_a}")
    c2.metric(f"{d_b['driver_name']} (wins)", f"{wins_b}")
    c3.metric("Drawn rounds", f"{draws}")

    team_h2h = h2h[h2h["team_name"] == team]
    if not team_h2h.empty:
        div = (
            alt.Chart(team_h2h)
            .mark_bar()
            .encode(
                x=alt.X("round:O", title="Round"),
                y=alt.Y("points_advantage:Q", title="Points advantage"),
                color=alt.condition(
                    alt.datum.points_advantage >= 0, alt.value(WIN), alt.value(LOSS)
                ),
                tooltip=[
                    "round",
                    "full_name",
                    "driver_points",
                    "teammate_points",
                    "points_advantage",
                ],
            )
            .properties(height=260)
        )
        st.subheader("Points advantage per round")
        st.altair_chart(div, width="stretch")

        pair_chart = (
            alt.Chart(pair)
            .mark_bar()
            .encode(
                x=alt.X("driver_name:N", title=None),
                y=alt.Y("total_points:Q", title="Season points"),
                color=alt.Color(
                    "driver_name:N",
                    scale=alt.Scale(
                        domain=[d_a["driver_name"], d_b["driver_name"]],
                        range=[TEAM_COLORS.get(team, "#888888"), "#333333"],
                    ),
                    legend=None,
                ),
                tooltip=["driver_name", "total_points", "h2h_wins", "rounds"],
            )
            .properties(height=260)
        )
        st.subheader("Season points by driver")
        st.altair_chart(pair_chart, width="stretch")

    st.subheader("Head-to-head detail")
    st.dataframe(team_h2h, hide_index=True, width="stretch")
    _download(team_h2h, "Teammate H2H")


def _render_race_results(season: int) -> None:
    rounds = load_rounds(season)
    if rounds.empty:
        st.info("No races for this season.")
        return
    round_names = dict(zip(rounds["round"], rounds["race_name"], strict=False))
    round_no = st.selectbox(
        "Round", rounds["round"], key="race_round", format_func=lambda r: f"R{r} — {round_names[r]}"
    )
    rr = load_race_results(season, int(round_no))
    if rr.empty:
        st.warning("No results for this round.")
        return

    winner = rr[rr["position"] == 1]
    podium = rr[rr["position"].isin([1, 2, 3])]
    m1, m2, m3 = st.columns(3)
    if not winner.empty:
        m1.metric("Winner", f"{winner.iloc[0]['full_name']} · {winner.iloc[0]['team_name']}")
    if not podium.empty:
        names = ", ".join(str(x) for x in podium["full_name"].tolist())
        m2.metric("Podium", names)
    finished = rr[rr["points"] > 0]
    m3.metric("Point scorers", f"{len(finished)}")

    gf = rr[["full_name", "team_name", "grid", "position"]].copy()
    gf["grid"] = pd.to_numeric(gf["grid"], errors="coerce")
    gf["position"] = pd.to_numeric(gf["position"], errors="coerce")
    gf = gf.dropna(subset=["grid", "position"])
    if not gf.empty:
        gf["gained"] = (gf["grid"] - gf["position"]).round(0).astype(int)
        chart = (
            alt.Chart(gf)
            .mark_bar()
            .encode(
                x=alt.X("full_name:N", title=None, sort="-y"),
                y=alt.Y("gained:Q", title="Positions gained (+) / lost (-)"),
                color=alt.condition(alt.datum.gained >= 0, alt.value(WIN), alt.value(LOSS)),
                tooltip=["full_name", "team_name", "grid", "position", "gained"],
            )
            .properties(height=320)
        )
        st.subheader("Grid vs finish")
        st.altair_chart(chart, width="stretch")

    pts = rr[rr["points"] > 0]
    if not pts.empty:
        chart = (
            alt.Chart(pts)
            .mark_bar()
            .encode(
                x=alt.X("full_name:N", title=None, sort="-y"),
                y=alt.Y("points:Q", title="Points"),
                color=alt.Color("team_name:N", scale=team_scale(), legend=None),
                tooltip=["full_name", "team_name", "position", "points"],
            )
            .properties(height=280)
        )
        st.subheader("Points scored")
        st.altair_chart(chart, width="stretch")

    st.subheader("Full results")
    st.dataframe(
        rr,
        hide_index=True,
        width="stretch",
        column_config={
            "full_name": "Driver",
            "team_name": "Team",
            "position": st.column_config.NumberColumn("Pos", format="%d"),
            "grid": st.column_config.NumberColumn("Grid", format="%d"),
            "points": st.column_config.NumberColumn("Points", format="%.1f"),
        },
    )
    _download(rr, "Race results")


def main() -> None:
    st.title("F1 Dashboard")

    meta = load_meta()
    st.caption(f"Last pipeline run: {_freshness(meta)}")

    seasons = load_seasons()
    if not seasons:
        st.info("No races in the database yet. Run `python main.py` first.")
        return

    season = st.sidebar.selectbox("Season", seasons)
    ds = load_driver_standings(season)
    drivers = ds["driver_id"].tolist() if not ds.empty else []
    names = ds.set_index("driver_id")["full_name"].to_dict() if not ds.empty else {}
    top_n = st.sidebar.slider(
        "Default drivers shown",
        min_value=1,
        max_value=max(3, len(drivers)),
        value=min(10, max(1, len(drivers))),
    )
    picked = st.sidebar.multiselect(
        "Drivers",
        options=drivers,
        default=drivers[:top_n],
        format_func=lambda d: names.get(d, d),
    )

    tab_hub, tab_trend, tab_positions, tab_h2h, tab_results = st.tabs(
        ["Season Hub", "Points Trend", "Race Positions", "Teammate H2H", "Race Results"]
    )

    with tab_hub:
        _render_season_hub(season)
    with tab_trend:
        _render_points_trend(season, picked)
    with tab_positions:
        _render_race_positions(season, picked)
    with tab_h2h:
        _render_teammate_h2h(season)
    with tab_results:
        _render_race_results(season)


if __name__ == "__main__":
    if st.runtime.exists():
        main()
    else:
        print(
            "This is a Streamlit app. Run it with:\n    streamlit run app.py\n(NOT: python app.py)"
        )
