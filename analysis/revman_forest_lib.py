import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
import numpy as np

matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.family"] = "DejaVu Sans"

GREEN = "#4f8f3f"
BLACK = "#111111"
GREY_TEXT = "#9a9a9a"
GRID = "#bcbcbc"
TITLEBAR = "#e7e7e7"
TOTAL_BLUE = "#1a3c8c"

STAR_RED = "#d62728"
STAR_GREEN = "#2e7d32"

SYMBOLS = {}


def revman_forest(
    title_bar_text,
    data_type,                      # "continuous" or "binary"
    groupA_name, groupB_name,
    effect_name, method_name,
    rows,
    total_est, total_lo, total_hi, total_nA, total_nB,
    het_lines, footnotes,
    xlim, xticks,
    favors_left, favors_right,
    log_scale,
    out_png, out_pdf,
    fig_w=16.5,
    _debug_return=False,
    star_col=False,
):
    n = len(rows)
    row_h = 0.60
    header_h1 = 0.55
    header_h2 = 0.55
    header_h = header_h1 + header_h2
    total_row_h = 0.68
    footer_h = 0.32 * (len(het_lines) + len(footnotes)) + 0.30

    # ---------- fit title: shrink, then wrap ----------
    left_panel_w = fig_w * 0.66 - 0.012 * fig_w
    usable_w = left_panel_w - 0.35

    def _text_w(s, fs):
        _f = plt.figure(figsize=(2, 2))
        _a = _f.add_axes([0, 0, 1, 1])
        _f.canvas.draw()
        _t = _a.text(0, 0, s, fontsize=fs, fontweight="bold")
        _f.canvas.draw()
        w = _t.get_window_extent(renderer=_f.canvas.get_renderer()).width / _f.dpi
        plt.close(_f)
        return w

    title_fs = 13.5
    title_lines = [title_bar_text]
    while title_fs > 10.0 and _text_w(title_bar_text, title_fs) > usable_w:
        title_fs -= 0.5
    if _text_w(title_bar_text, title_fs) > usable_w:
        if "  |  " in title_bar_text:
            a, b = title_bar_text.split("  |  ", 1)
            title_lines = [a + "  |", b]
        else:
            words = title_bar_text.split(" ")
            mid = len(words) // 2
            title_lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        while title_fs > 9.5 and max(_text_w(l, title_fs) for l in title_lines) > usable_w:
            title_fs -= 0.5

    titlebar_h = 0.62 if len(title_lines) == 1 else 0.98
    top_pad = titlebar_h + 0.18

    fig_h = top_pad + header_h + n * row_h + total_row_h + footer_h + 0.25
    fig = plt.figure(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")

    left_frac = 0.66
    gap = 0.008
    ax_l = fig.add_axes([0.012, 0.0, left_frac - 0.012, 1.0])
    ax_r = fig.add_axes([left_frac + gap, 0.0, 1 - left_frac - gap - 0.012, 1.0])
    for ax in (ax_l, ax_r):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, fig_h)
        ax.axis("off")
        ax.invert_yaxis()
        ax.set_facecolor("white")

    # ---------- title bar ----------
    ax_l.add_patch(Rectangle((0, 0), 1.0, titlebar_h, facecolor=TITLEBAR, edgecolor=GRID,
                             linewidth=0.8, clip_on=False, zorder=1))
    ax_r.add_patch(Rectangle((0, 0), 1.0, titlebar_h, facecolor=TITLEBAR, edgecolor=GRID,
                             linewidth=0.8, clip_on=False, zorder=1))
    ax_l.text(0.012, titlebar_h / 2, "\n".join(title_lines), fontsize=title_fs,
              fontweight="bold", va="center", ha="left", zorder=2, linespacing=1.25)

    # ---------- columns ----------
    if data_type == "continuous":
        col_study = (0.0, 0.24)
        colsA = [("Mean", 0.24, 0.315), ("SD", 0.315, 0.39), ("Total", 0.39, 0.45)]
        colsB = [("Mean", 0.45, 0.525), ("SD", 0.525, 0.60), ("Total", 0.60, 0.66)]
        col_w = (0.66, 0.75)
    else:
        col_study = (0.0, 0.28)
        colsA = [("Events", 0.28, 0.38), ("Total", 0.38, 0.46)]
        colsB = [("Events", 0.46, 0.56), ("Total", 0.56, 0.64)]
        col_w = (0.64, 0.75)
    col_eff = (0.75, 1.0)
    gA = (colsA[0][1], colsA[-1][2])
    gB = (colsB[0][1], colsB[-1][2])

    y0 = top_pad
    y_r1 = y0 + header_h1
    y_r2 = y0 + header_h

    ax_l.text((gA[0] + gA[1]) / 2, y0 + header_h1 / 2, groupA_name, fontsize=12.5,
              fontweight="bold", ha="center", va="center")
    ax_l.text((gB[0] + gB[1]) / 2, y0 + header_h1 / 2, groupB_name, fontsize=12.5,
              fontweight="bold", ha="center", va="center")
    ax_l.text((col_w[0] + col_w[1]) / 2, y0 + header_h / 2, "Weight", fontsize=11.5,
              fontweight="bold", ha="center", va="center")
    ax_l.text((col_eff[0] + col_eff[1]) / 2, y0 + header_h1 / 2, effect_name, fontsize=11.8,
              fontweight="bold", ha="center", va="center")
    ax_l.text((col_eff[0] + col_eff[1]) / 2, y0 + header_h1 + header_h2 / 2, method_name,
              fontsize=10.2, ha="center", va="center", color="#333333")
    ax_l.text((col_study[0] + col_study[1]) / 2, y0 + header_h / 2, "Study or Subgroup",
              fontsize=12.2, fontweight="bold", ha="center", va="center")
    for label, x0c, x1c in colsA + colsB:
        ax_l.text((x0c + x1c) / 2, y0 + header_h1 + header_h2 / 2, label, fontsize=11,
                  fontweight="bold", ha="center", va="center")

    ax_r.text(0.5, y0 + header_h1 / 2, effect_name, fontsize=12.5, fontweight="bold",
              ha="center", va="center")
    ax_r.text(0.5, y0 + header_h1 + header_h2 / 2, method_name, fontsize=10.6,
              ha="center", va="center", color="#333333")

    # ---------- dividers ----------
    y_tbl_top = y0
    y_tbl_bot = y0 + header_h + n * row_h + total_row_h
    outer = [col_study[1], colsA[-1][2], colsB[-1][2], col_w[1]]
    inner = [c[2] for c in colsA[:-1]] + [c[2] for c in colsB[:-1]]
    for xv in outer:
        ax_l.plot([xv, xv], [y_tbl_top, y_tbl_bot], color=GRID, lw=0.7, zorder=1)
    for xv in inner:
        ax_l.plot([xv, xv], [y_r1, y_tbl_bot], color=GRID, lw=0.7, zorder=1)
    ax_l.plot([0, 1], [y_r2, y_r2], color=BLACK, lw=1.1, zorder=2)
    ax_r.plot([0, 1], [y_r2, y_r2], color=BLACK, lw=1.1, zorder=2)
    for i in range(n):
        yy = y_r2 + i * row_h
        ax_l.plot([0, 1], [yy, yy], color=GRID, lw=0.5, zorder=1)
    y_before_total = y_r2 + n * row_h
    ax_l.plot([0, 1], [y_before_total, y_before_total], color=BLACK, lw=1.0, zorder=2)
    ax_r.plot([0, 1], [y_before_total, y_before_total], color=BLACK, lw=0.8, zorder=2)

    # ---------- forest mapping ----------
    def X(v):
        if log_scale:
            if v <= 0:
                v = xlim[0] * 5
            lo_l, hi_l = np.log10(xlim[0]), np.log10(xlim[1])
            return (np.log10(v) - lo_l) / (hi_l - lo_l)
        return (v - xlim[0]) / (xlim[1] - xlim[0])

    null_v = 1.0 if log_scale else 0.0
    ax_r.plot([X(null_v), X(null_v)], [y_r2, y_before_total], color=BLACK, lw=1.0, zorder=2)

    # ---------- rows ----------
    max_w = max([r["weight"] for r in rows if r.get("weight")], default=1)
    y = y_r2
    for r in rows:
        cy = y + row_h / 2
        color = GREY_TEXT if r.get("excluded") else BLACK
        star = r.get("star")
        both = star == "both"
        name_x0 = col_study[0] + (0.038 if (star_col and both) else 0.026 if star_col else 0.008)
        ax_l.text(name_x0, cy, r["name"] + (r.get("footnote") or ""),
                  fontsize=11.6, va="center", ha="left", color=color)
        if star_col and star:
            star_x = col_study[0] + 0.011
            if both:
                ax_l.plot(star_x, cy, marker="*", color=STAR_GREEN, markersize=15,
                          markeredgewidth=0.6, markeredgecolor="#2b2b2b", zorder=5, clip_on=False)
                ax_l.plot(star_x + 0.013, cy, marker="*", color=STAR_RED, markersize=15,
                          markeredgewidth=0.6, markeredgecolor="#2b2b2b", zorder=5, clip_on=False)
            else:
                star_color = STAR_RED if star == "red" else STAR_GREEN
                ax_l.plot(star_x, cy, marker="*", color=star_color, markersize=15,
                          markeredgewidth=0.6, markeredgecolor="#2b2b2b", zorder=5, clip_on=False)

        if data_type == "continuous":
            vals = [r["mA"], r["sA"], r["nA"], r["mB"], r["sB"], r["nB"]]
            for idx, ((label, x0c, x1c), v) in enumerate(zip(colsA + colsB, vals)):
                txt = f"{int(v):d}" if idx in (2, 5) else f"{v:.1f}"
                ax_l.text((x0c + x1c) / 2, cy, txt, fontsize=11.2, va="center",
                          ha="center", color=color)
        else:
            vals = [r["eA"], r["nA"], r["eB"], r["nB"]]
            for (label, x0c, x1c), v in zip(colsA + colsB, vals):
                ax_l.text((x0c + x1c) / 2, cy, f"{v:g}", fontsize=11.2, va="center",
                          ha="center", color=color)

        if r.get("excluded"):
            ax_l.text((col_w[0] + col_w[1]) / 2, cy, "\u2014", fontsize=11.2,
                      va="center", ha="center", color=color)
            ax_l.text((col_eff[0] + col_eff[1]) / 2, cy, "Not estimable", fontsize=10.4,
                      va="center", ha="center", color=color)
        else:
            ax_l.text((col_w[0] + col_w[1]) / 2, cy, f"{r['weight']:.1f}%", fontsize=11.2,
                      va="center", ha="center", color=color)
            eff_txt = f"{r['est']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}]"
            fs = 10.8 if len(eff_txt) <= 22 else 9.6
            ax_l.text((col_eff[0] + col_eff[1]) / 2, cy, eff_txt, fontsize=fs,
                      va="center", ha="center", color=color)

            x_lo, x_hi, x_est = X(r["lo"]), X(r["hi"]), X(r["est"])
            ax_r.plot([x_lo, x_hi], [cy, cy], color=BLACK, lw=1.2, zorder=3)
            ax_r.plot([x_lo, x_lo], [cy - 0.055, cy + 0.055], color=BLACK, lw=1.2, zorder=3)
            ax_r.plot([x_hi, x_hi], [cy - 0.055, cy + 0.055], color=BLACK, lw=1.2, zorder=3)
            # The marker is a true square in inches (x units are a fraction of
            # the right panel, y units are inches, so the two are converted).
            # Its side scales with weight and is then capped so the square never
            # reaches the null-effect line — a mark straddling the reference line
            # reads as an estimate that includes it, which weight does not mean.
            panel_w_in = fig_w * (1 - left_frac - gap - 0.012)
            side_in = 0.070 + 0.125 * np.sqrt(r["weight"] / max_w)
            side_in = min(side_in, row_h * 0.62)
            half_x = (side_in / panel_w_in) / 2
            x_null = X(1.0 if log_scale else 0.0)
            room = abs(x_est - x_null)
            if room > 0.005:
                half_x = min(half_x, room - 0.005)
            half_x = max(half_x, 0.0035)
            side_in = half_x * 2 * panel_w_in
            ax_r.add_patch(Rectangle((x_est - half_x, cy - side_in / 2),
                                     half_x * 2, side_in,
                                     facecolor=GREEN, edgecolor=GREEN, zorder=4))
        y += row_h

    # ---------- total ----------
    cy_t = y_before_total + total_row_h / 2
    ax_l.text(col_study[0] + 0.008, cy_t, "Total (95% CI)", fontsize=12,
              fontweight="bold", va="center", ha="left", color=TOTAL_BLUE)
    ax_l.text((colsA[-1][1] + colsA[-1][2]) / 2, cy_t, f"{total_nA:g}", fontsize=11.8,
              fontweight="bold", va="center", ha="center", color=TOTAL_BLUE)
    ax_l.text((colsB[-1][1] + colsB[-1][2]) / 2, cy_t, f"{total_nB:g}", fontsize=11.8,
              fontweight="bold", va="center", ha="center", color=TOTAL_BLUE)
    ax_l.text((col_w[0] + col_w[1]) / 2, cy_t, "100.0%", fontsize=11.8,
              fontweight="bold", va="center", ha="center", color=TOTAL_BLUE)
    ax_l.text((col_eff[0] + col_eff[1]) / 2, cy_t,
              f"{total_est:.2f} [{total_lo:.2f}, {total_hi:.2f}]", fontsize=11.3,
              fontweight="bold", va="center", ha="center", color=TOTAL_BLUE)

    x_lo, x_hi, x_est = X(total_lo), X(total_hi), X(total_est)
    dh = 0.15
    ax_r.add_patch(Polygon([[x_lo, cy_t], [x_est, cy_t - dh], [x_hi, cy_t], [x_est, cy_t + dh]],
                           closed=True, facecolor=BLACK, edgecolor=BLACK, zorder=5))

    y_tbl_end = y_before_total + total_row_h
    ax_l.plot([0, 1], [y_tbl_end, y_tbl_end], color=BLACK, lw=1.1, zorder=2)

    # ---------- axis ----------
    y_axis = y_tbl_end + 0.12
    ax_r.plot([0, 1], [y_axis, y_axis], color=BLACK, lw=1.0)
    for t in xticks:
        xt = X(t)
        ax_r.plot([xt, xt], [y_axis, y_axis + 0.055], color=BLACK, lw=1.0)
        ax_r.text(xt, y_axis + 0.16, f"{t:g}", fontsize=10.3, ha="center", va="top")
    y_fav = y_axis + 0.42
    ax_r.text(0.015, y_fav, favors_left, fontsize=11, ha="left", va="top")
    ax_r.text(0.985, y_fav, favors_right, fontsize=11, ha="right", va="top")

    # ---------- footer ----------
    fy = y_tbl_end + 0.34
    for line in het_lines:
        ax_l.text(0.012, fy, line, fontsize=10.4, color="#222222", va="center")
        fy += 0.32
    for line in footnotes:
        ax_l.text(0.012, fy, line, fontsize=9.6, color="#555555", va="center", style="italic")
        fy += 0.30

    for ax in (ax_l, ax_r):
        ax.add_patch(Rectangle((0, 0), 1, fig_h, fill=False, edgecolor="#888888",
                               linewidth=0.9, clip_on=False, zorder=6))

    if _debug_return:
        return fig, ax_l, ax_r, outer + inner, col_study, colsA, colsB, col_w, col_eff

    fig.savefig(out_png, dpi=400, bbox_inches="tight", pad_inches=0.18, facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.18, facecolor="white")
    plt.close(fig)
