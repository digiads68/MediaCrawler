# -*- coding: utf-8 -*-
"""Tính đà tăng (velocity) tuần-over-tuần cho post/creator."""

from __future__ import annotations

import pandas as pd


def weekly_velocity(df: pd.DataFrame, key: str = "creator_hash",
                    metric: str = "eng_total", min_rows: int = 2) -> pd.DataFrame:
    """
    Đà tăng WoW cho từng nhóm `key`: mean(metric) nửa sau / nửa đầu
    (sắp theo created_at). velocity > 1 nghĩa là đang lên.

    Trả DataFrame: [key, so_dong, nua_dau, nua_sau, velocity].
    """
    if key not in df.columns:
        raise ValueError(f"Thiếu cột khoá: {key}")
    if metric not in df.columns:
        raise ValueError(f"Thiếu cột chỉ số: {metric}")
    d = df.sort_values("created_at") if "created_at" in df.columns else df
    rows: list[dict] = []
    for gid, g in d.groupby(key):
        if len(g) < min_rows:
            continue
        vals = g[metric]
        half = len(g) // 2
        v1, v2 = vals.iloc[:half].mean(), vals.iloc[half:].mean()
        rows.append({
            key: gid,
            "so_dong": len(g),
            "nua_dau": round(float(v1), 1),
            "nua_sau": round(float(v2), 1),
            "velocity": round(float(v2 / v1), 2) if v1 > 0 else 1.0,
        })
    return pd.DataFrame(rows)
