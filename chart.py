"""Draws cost_per_day.png for the README from the model's own numbers."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
import model as M

a = M.A
rows = sorted([(label, M.design(a, "freezer", fn, fa)["per_day"]) for label, fn, fa in M.NAMED], key=lambda x: x[1])
rows.append(("Petrol generator, 8 h a day", M.generator_benchmark(a)[0]))
cheapest = min(v for _, v in rows[:4])

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
ACCENT, GREY, GREY_DARK = "#2a78d6", "#c9c7c0", "#8f8d86"

fig, ax = plt.subplots(figsize=(8.6, 4.4), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)
h, r = 0.42, 22.0                      # bar thickness (axis units), end rounding in naira
ys = list(range(len(rows)))[::-1]
for y, (label, v) in zip(ys, rows):
    col = ACCENT if v == cheapest else (GREY_DARK if "generator" in label else GREY)
    ax.add_patch(Rectangle((0, y - h / 2), v - r, h, color=col, lw=0))
    ax.add_patch(FancyBboxPatch((v - 2 * r, y - h / 2), 2 * r, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                color=col, lw=0, mutation_aspect=h / (2 * r)))
    ax.text(v + 60, y, f"₦{v:,.0f}", va="center", ha="left", fontsize=10, color=INK,
            fontweight="bold" if v == cheapest else "normal")
ax.set_yticks(ys, [l for l, _ in rows], fontsize=9.5, color=INK)
ax.set_xlim(0, 5200)
ax.set_ylim(-0.6, len(rows) - 0.4)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"₦{x:,.0f}"))
ax.tick_params(axis="x", colors=INK2, labelsize=8.5, length=0)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
for s in ax.spines.values():
    s.set_visible(False)
fig.text(0.015, 0.95, "Solar storage costs a fifth of a petrol generator; batteries are the cheapest store",
         fontsize=12, fontweight="bold", color=INK)
fig.text(0.015, 0.895, "Cost per day over 10 years to keep a 200 L chest freezer at −18 °C for a Lagos fish trader "
         "(today's naira, 13% real discount rate)", fontsize=8.8, color=INK2)
fig.text(0.015, 0.02, "Source: model.py in this repository; prices Sept–Nov 2026, several inputs estimated "
         "(see README).", fontsize=7.8, color=INK2)
plt.subplots_adjust(left=0.30, right=0.97, top=0.85, bottom=0.12)
fig.savefig("cost_per_day.png", facecolor=SURFACE)
print("wrote cost_per_day.png", [(l, round(v)) for l, v in rows])
