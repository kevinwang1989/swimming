"""Season report generator for an individual athlete.

Pure-Python, deterministic. Pulls data from existing queries, computes
key stats, and renders a Markdown narrative. LLM rewrite is left as a
future stub for when an API key is available.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from db.connection import get_db
from queries.results import get_participant_history
from queries.progress import get_progress_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_time(seconds: float) -> str:
    if seconds is None or pd.isna(seconds):
        return "—"
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f"{m}:{s:05.2f}"
    return f"{seconds:.2f}"


@st.cache_data(ttl=600)
def _peer_times(event_name: str, gender: str, group_name: str) -> list:
    """Return all valid finish times for the same event/gender/group across all comps.

    Used to compute percentile rank for the athlete's best swim.
    """
    conn = get_db()
    rows = conn.execute(
        """
        SELECT r.numeric_value
        FROM result r
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN group_def g  ON g.id = e.group_id
        JOIN event ev     ON ev.id = r.event_id
        WHERE ev.name = ?
          AND g.gender = ?
          AND g.group_name = ?
          AND r.status = 'normal'
          AND r.numeric_value IS NOT NULL
          AND r.numeric_value > 0
          AND ev.category = 'swimming'
          AND ev.result_type = 'time'
        """,
        (event_name, gender, group_name),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _percentile_rank(time_seconds: float, peer_times: list) -> float | None:
    """Return the top-percentile of `time_seconds` against `peer_times`.

    Lower time = better. Returns e.g. 12.5 meaning "top 12.5%".
    """
    if not peer_times or time_seconds is None or pd.isna(time_seconds):
        return None
    n = len(peer_times)
    if n < 2:
        return None
    faster_or_equal = sum(1 for t in peer_times if t <= time_seconds)
    return 100.0 * faster_or_equal / n


# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------


def build_report(participant_id: int) -> dict | None:
    """Return a structured report dict for one athlete, or None if no data."""
    history = get_participant_history(participant_id)
    if history.empty:
        return None

    # Filter to swimming + normal completions only
    swims = history[
        (history['category'] == 'swimming')
        & (history['status'] == 'normal')
        & (history['result_type'] == 'time')
        & history['numeric_value'].notna()
    ].copy()

    first = history.iloc[0]
    name = None  # filled by caller; participant table not joined here
    gender = first['gender']
    group_name = first['group_name']

    # ---- 参赛概况 ----
    overview = {
        'gender': gender,
        'group_name': group_name,
        'n_comps': int(history['competition'].nunique()),
        'n_events': int(swims['event_name'].nunique()) if not swims.empty else 0,
        'comps': history['competition'].unique().tolist(),
    }

    # Aggregate ranks across comps
    rank_rows = (
        history.groupby('competition', sort=False)
        .agg(rank=('rank', 'first'),
             total_score=('total_score', 'first'),
             rating=('rating', 'first'))
        .reset_index()
    )
    overview['ranks'] = rank_rows.to_dict('records')

    # ---- 最佳单项 ----
    best_event = None
    if not swims.empty:
        # For each unique event, take the athlete's BEST time across comps
        best_per_event = (
            swims.sort_values('numeric_value')
            .drop_duplicates(subset=['event_name'])
            .copy()
        )
        # Compute percentile for each
        best_per_event['percentile'] = best_per_event.apply(
            lambda row: _percentile_rank(
                row['numeric_value'],
                _peer_times(row['event_name'], gender, group_name),
            ),
            axis=1,
        )
        ranked = best_per_event.dropna(subset=['percentile']).sort_values('percentile')
        if not ranked.empty:
            top = ranked.iloc[0]
            best_event = {
                'event_name': top['event_name'],
                'time_seconds': float(top['numeric_value']),
                'time_str': _fmt_time(float(top['numeric_value'])),
                'percentile': float(top['percentile']),
                'competition': top['competition'],
            }

    # ---- 最大进步 ----
    biggest_improvement = None
    if overview['n_comps'] >= 2:
        progress_df = get_progress_data()
        my_progress = progress_df[progress_df['participant_id'] == participant_id]
        improved = my_progress[my_progress['delta_seconds'] < 0]
        if not improved.empty:
            top = improved.sort_values('delta_pct').iloc[0]
            biggest_improvement = {
                'event_name': top['event_name'],
                'earlier_time': _fmt_time(float(top['earlier_seconds'])),
                'later_time': _fmt_time(float(top['later_seconds'])),
                'earlier_comp': top['earlier_comp'],
                'later_comp': top['later_comp'],
                'delta_seconds': float(top['delta_seconds']),
                'delta_pct': float(top['delta_pct']),
            }

    # ---- 项目清单（按 percentile 升序，给底部小总结用） ----
    event_summary = []
    if not swims.empty:
        best_per_event = (
            swims.sort_values('numeric_value')
            .drop_duplicates(subset=['event_name'])
            .copy()
        )
        for _, row in best_per_event.iterrows():
            pct = _percentile_rank(
                row['numeric_value'],
                _peer_times(row['event_name'], gender, group_name),
            )
            event_summary.append({
                'event_name': row['event_name'],
                'best_time': _fmt_time(float(row['numeric_value'])),
                'percentile': pct,
            })
        event_summary.sort(key=lambda x: x['percentile'] if x['percentile'] is not None else 999)

    return {
        'overview': overview,
        'best_event': best_event,
        'biggest_improvement': biggest_improvement,
        'event_summary': event_summary,
    }


# ---------------------------------------------------------------------------
# Render markdown
# ---------------------------------------------------------------------------


def render_report_markdown(report: dict, name: str, district: str) -> str:
    """Render the report dict to a Markdown string."""
    if report is None:
        return f"暂无 **{name}** 的有效成绩数据。"

    ov = report['overview']
    lines = []
    lines.append(f"### 🌟 {name} · 2025-2026 赛季战报")
    lines.append(
        f"**{district} · {ov['gender']}子 {ov['group_name']} 组** "
        f"&nbsp;|&nbsp; 参加 {ov['n_comps']} 场比赛 "
        f"&nbsp;|&nbsp; 共 {ov['n_events']} 个游泳项目"
    )
    lines.append("")

    # ---- 综合表现 ----
    lines.append("#### 📊 综合表现")
    rank_lines = []
    for r in ov['ranks']:
        rank_val = r['rank']
        rank_text = (
            f"第 {int(rank_val)} 名"
            if rank_val is not None and not pd.isna(rank_val)
            else "—"
        )
        score_val = r['total_score']
        score_text = (
            f"总分 {score_val:.1f}"
            if score_val is not None and not pd.isna(score_val)
            else ""
        )
        rating_val = r['rating']
        rating_text = (
            f"评级 {rating_val}"
            if rating_val is not None
            and not (isinstance(rating_val, float) and pd.isna(rating_val))
            else ""
        )
        extras = " · ".join(t for t in [score_text, rating_text] if t)
        line = f"- **{r['competition']}** — {rank_text}"
        if extras:
            line += f" · {extras}"
        rank_lines.append(line)
    lines.extend(rank_lines)
    lines.append("")

    # ---- 最佳单项 ----
    if report['best_event']:
        be = report['best_event']
        pct = be['percentile']
        if pct <= 10:
            tone = "——达到「同组前 10%」的高水平 🏅"
        elif pct <= 25:
            tone = "——稳居同组前四分之一 ✨"
        elif pct <= 50:
            tone = "——位列同组中上游"
        else:
            tone = "——这是你冲击下一档位的目标项目"
        lines.append("#### 🏆 最佳单项")
        lines.append(
            f"你的最佳项目是 **{be['event_name']}**，最好成绩 **{be['time_str']}**，"
            f"在 {ov['gender']}子 {ov['group_name']} 组所有同项目选手中位列前 "
            f"**{pct:.1f}%**{tone}"
        )
        lines.append("")

    # ---- 最大进步 ----
    if report['biggest_improvement']:
        bi = report['biggest_improvement']
        lines.append("#### 🚀 最大进步")
        if bi['delta_pct'] <= -5:
            tone = "这是值得庆祝的飞跃！🎉"
        elif bi['delta_pct'] <= -2:
            tone = "扎实稳健的进步，继续保持。"
        else:
            tone = "小步快跑，积小胜为大胜。"
        lines.append(
            f"相比 **{bi['earlier_comp']}**，你的 **{bi['event_name']}** 进步最大："
        )
        lines.append(
            f"&nbsp;&nbsp;{bi['earlier_time']} → **{bi['later_time']}** &nbsp;"
            f"（快了 {abs(bi['delta_seconds']):.2f} 秒，{bi['delta_pct']:+.1f}%）"
        )
        lines.append(f"&nbsp;&nbsp;_{tone}_")
        lines.append("")
    elif ov['n_comps'] >= 2:
        lines.append("#### 🚀 跨站对比")
        lines.append("两场比赛的同项目成绩没有出现明显进步——")
        lines.append("但稳定本身也是实力，下一站继续冲击 PB。")
        lines.append("")

    # ---- 项目雷达 ----
    if report['event_summary']:
        lines.append("#### 📋 全部游泳项目（按同组排位）")
        lines.append("")
        lines.append("| 项目 | 最好成绩 | 同组前 % |")
        lines.append("|---|---|---|")
        for ev in report['event_summary']:
            pct_str = f"{ev['percentile']:.1f}%" if ev['percentile'] is not None else "—"
            lines.append(f"| {ev['event_name']} | {ev['best_time']} | {pct_str} |")
        lines.append("")

    lines.append("")
    lines.append("---")
    lines.append(
        "_战报基于本系统已导入比赛的数据自动生成；排位百分比 = 你在同组别同性别"
        "所有完赛同项目选手中的位置（数值越小越好）。_"
    )

    return "\n".join(lines)


def rewrite_with_llm(report: dict, name: str, district: str, provider: str = None) -> str:
    """Optional LLM rewrite hook. Returns template markdown if no provider."""
    # Future: when an LLM API key is available, plug in here.
    return render_report_markdown(report, name, district)
