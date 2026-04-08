"""Insight generation for event-level data.

Pure-Python module that consumes a DataFrame from `queries.results.get_event_results()`
and produces structured analysis dicts containing auto-generated Chinese narratives.

Public API:
    analyze_district(event_df, event_name, district)
    compare_districts(event_df, event_name, district_a, district_b)
    compare_athletes(event_df, event_name, picked_labels)

Each function returns:
    {
        "summary": str,
        "bullets": [str, ...],
        "segment_stats": pd.DataFrame | None,
        "warnings": [str, ...],
    }
"""

from __future__ import annotations

import pandas as pd

# Differences smaller than this (in seconds) are reported as "持平".
EPS = 0.10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_im(event_name: str) -> bool:
    return '个人混合泳' in event_name or '个混' in event_name


def _fmt_time(seconds: float) -> str:
    """Format seconds as M:SS.SS or SS.SS."""
    if seconds is None or pd.isna(seconds):
        return '—'
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f"{m}:{s:05.2f}"
    return f"{seconds:.2f}"


def _segment_label(seg: dict, is_im: bool, n_segs: int, idx: int) -> str:
    """Generate a human label for a segment.

    For IM events, use stroke + cumulative distance (e.g., "仰泳100m").
    For other events, use 前/中/后 + 距离 description.
    """
    dist = seg.get('dist', (idx + 1) * 50)
    if is_im and seg.get('stroke'):
        return f"{seg['stroke']}{dist}m"
    if n_segs == 2:
        return f"{'前' if idx == 0 else '后'}{dist - (0 if idx else 0)}m段" if False else (
            f"前{dist}m" if idx == 0 else f"后{dist - (idx) * 50}m"
        )
    # Generic label
    return f"{dist}m段"


def _generic_seg_labels(splits_lists, is_im: bool) -> list[str]:
    """Build a list of segment labels by inspecting the first non-empty split list.

    Returns a list of length = max segment count across rows. For IM events, the
    stroke comes from whichever row has it set.
    """
    n_segs = max((len(s) for s in splits_lists), default=0)
    labels: list[str] = []
    for i in range(n_segs):
        # Find the first row that has stroke for this segment (IM)
        chosen = None
        for s in splits_lists:
            if i < len(s) and s[i]:
                chosen = s[i]
                if is_im and chosen.get('stroke'):
                    break
        if chosen is None:
            labels.append(f"第{i+1}段")
            continue
        dist = chosen.get('dist', (i + 1) * 50)
        if is_im and chosen.get('stroke'):
            labels.append(f"{chosen['stroke']}{dist}m")
        else:
            # 前程 / 后程 for 2 segments; otherwise use distance label
            if n_segs == 2:
                labels.append(f"前{dist}m" if i == 0 else f"后{dist // 2}m")
            else:
                labels.append(f"{dist}m段")
    return labels


def _laps_matrix(rows_df: pd.DataFrame, n_segs: int) -> pd.DataFrame:
    """Extract a (rows × n_segs) matrix of lap times from a DataFrame.

    Missing/invalid laps become NaN. Returns a DataFrame indexed like rows_df.
    """
    data = []
    for _, row in rows_df.iterrows():
        splits = row['splits'] or []
        laps = []
        for i in range(n_segs):
            if i < len(splits):
                lap = splits[i].get('lap')
                laps.append(lap if lap is not None else float('nan'))
            else:
                laps.append(float('nan'))
        data.append(laps)
    return pd.DataFrame(data, index=rows_df.index)


# ---------------------------------------------------------------------------
# 1. Single-district analysis
# ---------------------------------------------------------------------------

def analyze_district(event_df: pd.DataFrame, event_name: str, district: str) -> dict:
    bullets: list[str] = []
    warnings: list[str] = []

    normal = event_df[event_df['status'] == 'normal'].copy()
    if normal.empty:
        return {
            'summary': '该项目暂无有效成绩可供分析。',
            'bullets': [], 'segment_stats': None, 'warnings': [],
        }

    sub = normal[normal['district'] == district]
    if sub.empty:
        return {
            'summary': f'{district} 在该项目中没有完赛选手。',
            'bullets': [], 'segment_stats': None, 'warnings': [],
        }

    n_district = len(sub)
    n_total = len(normal)
    if n_district < 3:
        warnings.append(f'⚠️ {district} 仅 {n_district} 名完赛选手，样本量较小，结论仅供参考。')
    if n_total < 5:
        warnings.append(f'⚠️ 该项目全体仅 {n_total} 名完赛选手，统计意义有限。')

    is_im = _is_im(event_name)

    # ---- Total time analysis ----
    all_times = normal['numeric_value'].dropna()
    dist_times = sub['numeric_value'].dropna()
    all_mean = all_times.mean() if not all_times.empty else None
    dist_mean = dist_times.mean() if not dist_times.empty else None

    # Percentile of district mean against all (lower time = better → smaller percentile)
    pct_text = ''
    if all_mean is not None and dist_mean is not None and not all_times.empty:
        rank_pos = (all_times < dist_mean).sum()
        pct = rank_pos / len(all_times) * 100
        pct_text = f'，处于全体前 {pct:.0f}%' if pct <= 50 else f'，处于全体后 {100 - pct:.0f}%'

    # ---- Segment analysis ----
    splits_all = normal['splits'].tolist()
    n_segs = max((len(s) for s in splits_all), default=0)
    seg_stats_df = None
    best_seg = None
    worst_seg = None

    if n_segs > 0:
        seg_labels = _generic_seg_labels(splits_all, is_im)

        all_lap_mat = _laps_matrix(normal, n_segs)
        dist_lap_mat = _laps_matrix(sub, n_segs)

        records = []
        for i in range(n_segs):
            all_col = all_lap_mat[i].dropna()
            dist_col = dist_lap_mat[i].dropna()
            if all_col.empty or dist_col.empty:
                continue
            a_mean = all_col.mean()
            a_std = all_col.std(ddof=0)
            d_mean = dist_col.mean()
            diff = d_mean - a_mean  # negative = faster than overall
            z = diff / a_std if a_std and a_std > 0 else 0.0
            records.append({
                '段': seg_labels[i],
                f'{district}均值': round(d_mean, 2),
                '全体均值': round(a_mean, 2),
                '差值': round(diff, 2),
                'z': round(z, 2),
            })

        if records:
            seg_stats_df = pd.DataFrame(records)
            ranked = sorted(records, key=lambda r: r['z'])  # ascending: most advantaged first
            best_seg = ranked[0]
            worst_seg = ranked[-1]

            for r in ranked:
                if r['差值'] < -EPS:
                    bullets.append(
                        f"✅ **{r['段']}**：区均值 {r[f'{district}均值']:.2f}s，"
                        f"比全体均值快 {abs(r['差值']):.2f}s（z={r['z']:+.2f}）"
                    )
                elif r['差值'] > EPS:
                    bullets.append(
                        f"⚠️ **{r['段']}**：区均值 {r[f'{district}均值']:.2f}s，"
                        f"比全体均值慢 {r['差值']:.2f}s（z={r['z']:+.2f}）"
                    )
                else:
                    bullets.append(
                        f"⚖️ **{r['段']}**：区均值 {r[f'{district}均值']:.2f}s，与全体基本持平"
                    )

    # ---- Summary line ----
    parts = [f"**{district}** 在该项目共 {n_district} 名完赛选手"]
    if dist_mean is not None:
        parts.append(f"，平均成绩 {_fmt_time(dist_mean)}{pct_text}")
    if best_seg is not None and best_seg['差值'] < -EPS:
        parts.append(
            f"。最具优势的分段是 **{best_seg['段']}**"
            f"（区内均值 {best_seg[f'{district}均值']:.2f}s，"
            f"领先全体 {abs(best_seg['差值']):.2f}s）"
        )
        if worst_seg is not None and worst_seg['差值'] > EPS:
            parts.append(
                f"；最薄弱的分段是 **{worst_seg['段']}**"
                f"（落后 {worst_seg['差值']:.2f}s）"
            )
        parts.append('。')
    elif best_seg is not None:
        parts.append('。各分段相对全体均值无显著优势。')
    else:
        parts.append('。')

    return {
        'summary': ''.join(parts),
        'bullets': bullets,
        'segment_stats': seg_stats_df,
        'warnings': warnings,
    }


# ---------------------------------------------------------------------------
# 2. Two-district comparison
# ---------------------------------------------------------------------------

def compare_districts(
    event_df: pd.DataFrame, event_name: str, district_a: str, district_b: str,
) -> dict:
    bullets: list[str] = []
    warnings: list[str] = []

    normal = event_df[event_df['status'] == 'normal'].copy()
    sub_a = normal[normal['district'] == district_a]
    sub_b = normal[normal['district'] == district_b]

    if sub_a.empty or sub_b.empty:
        missing = [d for d, s in [(district_a, sub_a), (district_b, sub_b)] if s.empty]
        return {
            'summary': f'{"、".join(missing)} 在该项目中没有完赛选手，无法对比。',
            'bullets': [], 'segment_stats': None, 'warnings': [],
        }

    n_a, n_b = len(sub_a), len(sub_b)
    if n_a < 3 or n_b < 3:
        warnings.append(
            f'⚠️ 样本量较小（{district_a} {n_a} 人 / {district_b} {n_b} 人），结论仅供参考。'
        )

    is_im = _is_im(event_name)

    # ---- Total time ----
    a_total = sub_a['numeric_value'].dropna().mean()
    b_total = sub_b['numeric_value'].dropna().mean()
    total_diff = a_total - b_total  # negative = A faster

    # ---- Segments ----
    splits_all = normal['splits'].tolist()
    n_segs = max((len(s) for s in splits_all), default=0)
    seg_stats_df = None
    a_advantages: list[str] = []
    b_advantages: list[str] = []

    if n_segs > 0:
        seg_labels = _generic_seg_labels(splits_all, is_im)
        a_mat = _laps_matrix(sub_a, n_segs)
        b_mat = _laps_matrix(sub_b, n_segs)

        records = []
        for i in range(n_segs):
            ac = a_mat[i].dropna()
            bc = b_mat[i].dropna()
            if ac.empty or bc.empty:
                continue
            am, bm = ac.mean(), bc.mean()
            diff = am - bm
            records.append({
                '段': seg_labels[i],
                f'{district_a}均值': round(am, 2),
                f'{district_b}均值': round(bm, 2),
                '差值': round(diff, 2),
            })

            if diff < -EPS:
                bullets.append(
                    f"✅ **{seg_labels[i]}**：{district_a} 领先 {abs(diff):.2f}s "
                    f"（{am:.2f} vs {bm:.2f}）"
                )
                a_advantages.append(seg_labels[i])
            elif diff > EPS:
                bullets.append(
                    f"⚠️ **{seg_labels[i]}**：{district_b} 领先 {diff:.2f}s "
                    f"（{am:.2f} vs {bm:.2f}）"
                )
                b_advantages.append(seg_labels[i])
            else:
                bullets.append(
                    f"⚖️ **{seg_labels[i]}**：两区基本持平"
                    f"（{am:.2f} vs {bm:.2f}）"
                )

        if records:
            seg_stats_df = pd.DataFrame(records)

    # ---- Summary ----
    if abs(total_diff) < EPS:
        verdict = f"两区均速基本持平（差距 {abs(total_diff):.2f}s）"
    elif total_diff < 0:
        verdict = f"**{district_a} 整体领先 {abs(total_diff):.2f}s**"
    else:
        verdict = f"**{district_b} 整体领先 {total_diff:.2f}s**"
    summary = (
        f"{district_a}（{n_a} 人，均速 {_fmt_time(a_total)}） vs "
        f"{district_b}（{n_b} 人，均速 {_fmt_time(b_total)}）：{verdict}。"
    )

    # Closing narrative bullet summarizing advantage distribution
    if a_advantages or b_advantages:
        parts = []
        if a_advantages:
            parts.append(f"{district_a} 在 {'、'.join(a_advantages)} 上更强")
        if b_advantages:
            parts.append(f"{district_b} 在 {'、'.join(b_advantages)} 上更强")
        bullets.append('🏁 ' + '；'.join(parts) + '。')

    return {
        'summary': summary,
        'bullets': bullets,
        'segment_stats': seg_stats_df,
        'warnings': warnings,
    }


# ---------------------------------------------------------------------------
# 3. Athlete-vs-athlete comparison
# ---------------------------------------------------------------------------

def compare_athletes(
    event_df: pd.DataFrame, event_name: str, picked_labels: list[str],
) -> dict:
    """picked_labels: list of "姓名（代表队）" strings, matching the multiselect format."""
    warnings: list[str] = []
    bullets: list[str] = []

    normal = event_df[event_df['status'] == 'normal'].copy()
    normal['label'] = normal['name'] + '（' + normal['district'] + '）'

    rows = []
    for lbl in picked_labels:
        match = normal[normal['label'] == lbl]
        if not match.empty:
            rows.append(match.iloc[0])
    if len(rows) < 2:
        return {
            'summary': '请选择至少 2 名选手进行对比。',
            'bullets': [], 'segment_stats': None, 'warnings': [],
        }

    is_im = _is_im(event_name)
    splits_all = [r['splits'] for r in rows]
    n_segs = max((len(s) for s in splits_all), default=0)
    seg_labels = _generic_seg_labels(splits_all, is_im) if n_segs > 0 else []

    base = rows[0]
    base_total = base['numeric_value']
    base_label = base['label']

    # ---- Total comparison vs each other athlete ----
    summary_parts = [f"以 **{base_label}**（{_fmt_time(base_total)}）为基准："]
    for r in rows[1:]:
        diff = (r['numeric_value'] or 0) - (base_total or 0)
        if base_total is None or r['numeric_value'] is None:
            continue
        if abs(diff) < EPS:
            summary_parts.append(f"{r['label']} 与基准持平。")
        elif diff > 0:
            summary_parts.append(
                f"{r['label']}（{_fmt_time(r['numeric_value'])}）慢 {diff:.2f}s。"
            )
        else:
            summary_parts.append(
                f"{r['label']}（{_fmt_time(r['numeric_value'])}）快 {abs(diff):.2f}s。"
            )
    summary = ' '.join(summary_parts)

    # ---- Segment-by-segment ----
    seg_stats_df = None
    if n_segs > 0:
        # Build matrix of laps for each picked athlete
        records = []
        for i in range(n_segs):
            base_lap = (base['splits'][i].get('lap')
                        if i < len(base['splits']) else None)
            row = {'段': seg_labels[i] if i < len(seg_labels) else f'第{i+1}段',
                   base_label: round(base_lap, 2) if base_lap is not None else None}
            for r in rows[1:]:
                splits = r['splits']
                lap = splits[i].get('lap') if i < len(splits) else None
                row[r['label']] = round(lap, 2) if lap is not None else None
            records.append(row)
        seg_stats_df = pd.DataFrame(records)

        # Per-segment advantage narrative (only for 2-athlete case → cleanest narrative)
        if len(rows) == 2:
            other = rows[1]
            other_label = other['label']
            cum_diff = 0.0
            seg_diffs = []
            for i in range(n_segs):
                bl = base['splits'][i].get('lap') if i < len(base['splits']) else None
                ol = other['splits'][i].get('lap') if i < len(other['splits']) else None
                if bl is None or ol is None:
                    continue
                d = ol - bl  # positive = base faster
                cum_diff += d
                seg_diffs.append((seg_labels[i] if i < len(seg_labels) else f'第{i+1}段',
                                  bl, ol, d))
                if abs(d) < EPS:
                    bullets.append(
                        f"⚖️ **{seg_labels[i]}**：两人基本持平（{bl:.2f} vs {ol:.2f}）"
                    )
                elif d > 0:
                    bullets.append(
                        f"✅ **{seg_labels[i]}**：{base_label} 领先 {d:.2f}s "
                        f"（{bl:.2f} vs {ol:.2f}）"
                    )
                else:
                    bullets.append(
                        f"⚠️ **{seg_labels[i]}**：{other_label} 追回 {abs(d):.2f}s "
                        f"（{bl:.2f} vs {ol:.2f}）"
                    )

            if seg_diffs:
                key_seg = max(seg_diffs, key=lambda x: abs(x[3]))
                if abs(key_seg[3]) >= EPS:
                    direction = base_label if key_seg[3] > 0 else other_label
                    bullets.append(
                        f"🎯 **关键差距来自 {key_seg[0]}**："
                        f"{direction} 在该段建立了 {abs(key_seg[3]):.2f}s 的优势。"
                    )
        else:
            bullets.append('（多人对比时仅展示分段表，详细叙述以 2 人对比为佳。）')

    return {
        'summary': summary,
        'bullets': bullets,
        'segment_stats': seg_stats_df,
        'warnings': warnings,
    }
