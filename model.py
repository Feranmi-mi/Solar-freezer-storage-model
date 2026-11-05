"""
Battery or cold? Storage choice for a solar chest freezer in Lagos
Feranmi Adedipe, follow-on to the PCM cold-transport model

The question
  A fish trader's 200-litre solar chest freezer has to keep fish frozen through the
  night and through runs of cloudy rainy-season days. That stored energy can sit in a
  lithium battery (electricity, turned into cold later) or in a phase change material
  (PCM) inside the cabinet (cold made in the daytime and kept). Which is cheaper over
  10 years, and what is the best mix?

How it works
  1. Daily cooling load: heat through the walls, door openings, restocking.
  2. Storage the system needs: the hours without sun each day ("night"), plus a reserve
     for cloudy days ("autonomy").
  3. Each design splits each of those two stores between battery and PCM.
       f_night = share of the nightly store held as PCM
       f_auto  = share of the cloudy-day reserve held as PCM
  4. For each split: battery size, PCM mass and volume, compressor size, solar array,
     then 10 years of costs (replacements, upkeep, salvage) at a real discount rate.
  5. The PCM's supercooling decides how cold the compressor must run to refreeze it,
     which lowers efficiency and capacity, and past a limit makes it impossible.

Every input sits in A with a tag:
  [market] published price or data (see README)   [datasheet] manufacturer data
  [lit]    published research value                [est] estimate, replace with a quote

Run:  python model.py          (needs numpy only)
"""
import copy
import numpy as np

A = dict(
    # ---------------- appliance modes ----------------
    modes={
        "freezer": dict(
            label="Freezer, fish held at -18 °C (frozen fish trade)",
            t_cabinet=-18.0,
            t_evap_normal=-25.0,      # [datasheet] typical low-back-pressure rating point
            cop_normal=1.0,           # [datasheet] Secop BD35F at -25 °C: 0.83-1.24 W/W by standard and speed
            leak_kwh_day=0.90,        # [datasheet/est] SunDanzer DCF238: 938 Wh/day electric at 32 °C, x COP ~1.0, scaled to 200 L
            restock_kg_day=10.0,      # [est] frozen fish bought from a cold room
            restock_kj_per_kg=60.0,   # [est] fish that warmed to about -5 °C in transit, brought back to -18 °C
            base_capacity_w=65.0,     # [datasheet/est] one BD-class DC compressor at -25 °C, max speed
            pcm=dict(name="salt-water eutectic (23 wt% NaCl)", t_melt=-21.2,   # [lit] -21.2 °C
                     latent_kj_kg=225.0,      # [lit] about 220-235 kJ/kg reported
                     density=1.17,            # [lit]
                     supercool_k=2.0,         # [est] with a nucleating agent
                     material_ngn_kg=320.0,   # [est] 23% salt at ~N800/kg + water + nucleator
                     ),
        ),
        "chiller": dict(
            label="Chiller, fish held at +3 °C on 'ice' (fresh fish)",
            t_cabinet=3.0,
            t_evap_normal=-5.0,
            cop_normal=1.8,           # [datasheet] BD35F at -10 °C: 1.35-1.85 W/W; higher at -5 °C
            leak_kwh_day=0.52,        # [est] freezer leak x (32-3)/(32+18)
            restock_kg_day=10.0,      # [est] fresh fish
            restock_kj_per_kg=90.0,   # [est] 3.6 kJ/kg.K x (28 -> 3 °C)
            base_capacity_w=100.0,    # [datasheet/est]
            pcm=dict(name="water ice", t_melt=0.0, latent_kj_kg=334.0, density=1.0,
                     supercool_k=3.0, material_ngn_kg=100.0),
        ),
    },
    t_ambient=30.0,            # [est] daily mean at a Lagos market stall, °C
    rating_ambient=32.0,       # [datasheet] ambient behind the leak figure
    door_factor=1.15,          # [est] extra heat from opening the lid to sell

    # ---------------- sun and storage ----------------
    sun_hours=7.0,             # [est] hours a day the panels can run the compressor
    pv_yield_worst=4.46,       # [market] Lagos rainy-season PV yield, kWh per kWp per day (NASA POWER)
    pv_derate=0.80,            # [est] heat, dust, wiring and controller losses
    autonomy_days=3.0,         # [est] cloudy-day reserve (Koolboks quotes up to 4 days)
    recovery_days=4.0,         # [est] days to rebuild the reserve after a cloudy spell

    # ---------------- refrigeration physics ----------------
    approach_k=3.0,            # [est] evaporator must sit this far below the PCM's freezing point
    cop_slope=0.023,           # [datasheet] BD35F: COP falls ~1.9-2.6% per K of lower evaporating temp
    cap_slope=0.055,           # [datasheet] BD35F: capacity falls ~5-6.5% per K
    t_evap_min=-30.0,          # [datasheet] BD35F lowest evaporating temperature
    cap_margin=1.2,            # [est] compressor sizing margin

    # ---------------- PCM packaging ----------------
    panel_ngn_kg=750.0,        # [est] sealed HDPE panels, ~N1,500 per 2 kg
    pcm_usable=0.90,           # [est] share of latent heat actually used each cycle
    pcm_volume_overhead=1.20,  # [est] panel walls and air gaps
    pcm_upkeep=0.05,           # [est] share of PCM cost replaced each year (leaks, damage)
    cabinet_ngn_per_l=2000.0,  # [est] extra cost per litre of bigger cabinet to keep 200 L usable

    # ---------------- prices (today's naira) ----------------
    base_freezer_ngn=650_000,  # [est] 200 L DC chest freezer with one compressor
    compressor_ngn_per_w=4000, # [est] extra compressor capacity, per W of cooling at -25 °C
    pv_panel_ngn_per_w=290,    # [market] 550 W panels at N125,000-175,000 (Oct 2026)
    pv_bos_fixed=120_000,      # [est] MPPT controller, mounting, cables
    pv_bos_ngn_per_w=60,       # [est]
    battery_ngn_per_kwh=160_000,  # [market] LiFePO4 12 V 200 Ah at N315,000-470,000 (Sept 2026)
    battery_dod=0.90,          # [datasheet] LiFePO4
    battery_eff_out=0.95,      # [est] discharge and inverter-free DC losses
    battery_rt=0.92,           # [datasheet/est] round-trip efficiency
    battery_cycles=3000,       # [est] generic LiFePO4 sold in Nigeria (quality brands quote 6,000)
    battery_calendar_yr=8.0,   # [est] life limit in a hot climate
    battery_min_kwh=0.30,      # [est] still needed for controls and compressor start-up
    om_pct=0.015,              # [est] yearly upkeep, share of non-battery capex
    pv_life_yr=25.0,           # [datasheet]

    # ---------------- finance ----------------
    years=10,
    discount_real=0.13,        # [est] ~27% naira cost of capital less ~12% inflation

    # ---------------- benchmark: AC freezer on a petrol generator ----------------
    gen=dict(freezer_ngn=450_000,      # [est] 200 L AC chest freezer
             generator_ngn=90_000,     # [market] Sumec Firman SPG1200, 0.9 kVA
             generator_life_yr=1.5,    # [est]
             fuel_l_per_h=0.35,        # [est] light load (0.45 L/h quoted at half load)
             hours_per_day=8.0,        # [est] enough to keep fish frozen between runs
             petrol_ngn_l=1400.0,      # [market] Lagos depot ~N1,348/L (Oct 2026) plus retail margin
             maintenance_ngn_month=8000),  # [est] oil, plugs, repairs
)


# ======================================================================
# 1. LOADS AND STORAGE
# ======================================================================
def daily_load_kwh(a, m):
    """Thermal kWh/day the freezer must remove."""
    scale = (a["t_ambient"] - m["t_cabinet"]) / (a["rating_ambient"] - m["t_cabinet"])
    walls = m["leak_kwh_day"] * scale * a["door_factor"]
    restock = m["restock_kg_day"] * m["restock_kj_per_kg"] / 3600
    return walls + restock, walls, restock


def stores(a, m):
    load, _, _ = daily_load_kwh(a, m)
    night = load * (24 - a["sun_hours"]) / 24
    auto = load * a["autonomy_days"]
    return load, night, auto


def pcm_evap(a, m, supercool=None):
    p = m["pcm"]
    sc = p["supercool_k"] if supercool is None else supercool
    t_evap = p["t_melt"] - sc - a["approach_k"]
    dk = max(0.0, m["t_evap_normal"] - t_evap)
    return t_evap, dk, t_evap >= a["t_evap_min"]


# ======================================================================
# 2. SIZE AND COST ONE DESIGN
# ======================================================================
def design(a, mode, f_night, f_auto, supercool=None):
    m = a["modes"][mode]
    p = m["pcm"]
    load, night, auto = stores(a, m)
    uses_pcm = f_night > 0 or f_auto > 0
    t_evap, dk, ok = pcm_evap(a, m, supercool)
    if uses_pcm and not ok:
        return None                                   # compressor cannot get cold enough
    cop_n = m["cop_normal"]
    cop_p = cop_n * (1 - a["cop_slope"] * dk) if uses_pcm else cop_n

    # storage split
    pcm_kwh = f_night * night + f_auto * auto
    bat_kwh_th = (1 - f_night) * night + (1 - f_auto) * auto
    pcm_kg = pcm_kwh * 3600 / (p["latent_kj_kg"] * a["pcm_usable"])
    pcm_l = pcm_kg / p["density"] * a["pcm_volume_overhead"]
    bat_kwh = max(a["battery_min_kwh"], bat_kwh_th / cop_n / (a["battery_dod"] * a["battery_eff_out"]))

    # electricity on a normal day, plus rebuilding the reserve after a cloudy spell
    e_day = ((load - night) / cop_n
             + f_night * night / cop_p
             + (1 - f_night) * night / cop_n / a["battery_rt"])
    e_rec = (f_auto * auto / cop_p + (1 - f_auto) * auto / cop_n / a["battery_rt"]) / a["recovery_days"]
    pv_kwp = (e_day + e_rec) / (a["pv_yield_worst"] * a["pv_derate"])

    # compressor: everything the PCM stores must be frozen in the sun hours
    sun_w = ((load - night) + f_night * night + f_auto * auto / a["recovery_days"]) * 1000 / a["sun_hours"]
    night_w = (1 - f_night) * night * 1000 / (24 - a["sun_hours"])
    derate = 1 - a["cap_slope"] * dk if uses_pcm else 1.0
    need_w = max(sun_w / derate, night_w) * a["cap_margin"]
    extra_w = max(0.0, need_w - m["base_capacity_w"])

    capex = {
        "freezer": a["base_freezer_ngn"],
        "extra compressor": extra_w * a["compressor_ngn_per_w"],
        "PCM + panels": pcm_kg * (p["material_ngn_kg"] + a["panel_ngn_kg"]),
        "bigger cabinet": pcm_l * a["cabinet_ngn_per_l"],
        "battery": bat_kwh * a["battery_ngn_per_kwh"],
        "solar": (a["pv_bos_fixed"] + pv_kwp * 1000 * (a["pv_panel_ngn_per_w"] + a["pv_bos_ngn_per_w"])),
    }

    # battery life
    daily_out = (1 - f_night) * night / cop_n / a["battery_eff_out"]
    efc_yr = 365 * daily_out / bat_kwh + 10            # + ~10 cloudy-spell cycles a year
    bat_life = min(a["battery_cycles"] / efc_yr, a["battery_calendar_yr"])

    # 10-year present cost in today's naira
    r, n = a["discount_real"], a["years"]
    df = lambda t: 1 / (1 + r) ** t
    pc = {k: v for k, v in capex.items()}
    non_bat = sum(v for k, v in capex.items() if k != "battery")
    t = bat_life
    while t < n:
        pc["battery"] += capex["battery"] * df(t)
        t += bat_life
    left = (t - n) / bat_life                           # unused share of the last battery
    pc["battery"] -= capex["battery"] * left * df(n)
    upkeep = sum(df(y) for y in range(1, n + 1))
    pc["PCM + panels"] += capex["PCM + panels"] * a["pcm_upkeep"] * upkeep
    pc["upkeep"] = non_bat * a["om_pct"] * upkeep
    pc["solar"] -= pv_kwp * 1000 * a["pv_panel_ngn_per_w"] * (1 - n / a["pv_life_yr"]) * df(n)
    total = sum(pc.values())
    crf = r / (1 - (1 + r) ** -n)
    return dict(mode=mode, f_night=f_night, f_auto=f_auto, load=load, night=night, auto=auto,
                cop_p=cop_p, t_evap=t_evap, pcm_kg=pcm_kg, pcm_l=pcm_l, bat_kwh=bat_kwh, bat_life=bat_life,
                pv_kwp=pv_kwp, need_w=need_w, capex=capex, upfront=sum(capex.values()), pc=pc,
                total=total, per_day=total * crf / 365)


NAMED = [
    ("Battery only", 0.0, 0.0),
    ("PCM for nights, battery for cloudy days", 1.0, 0.0),
    ("Battery for nights, PCM for cloudy days", 0.0, 1.0),
    ("PCM only (direct drive)", 1.0, 1.0),
]


def best(a, mode, supercool=None, step=0.1):
    grid = np.round(np.arange(0, 1 + 1e-9, step), 2)
    cands = [design(a, mode, fn, fa, supercool) for fn in grid for fa in grid]
    cands = [c for c in cands if c]
    return min(cands, key=lambda c: c["total"]) if cands else None


def generator_benchmark(a):
    g = a["gen"]
    r, n = a["discount_real"], a["years"]
    df = lambda t: 1 / (1 + r) ** t
    yearly = (g["fuel_l_per_h"] * g["hours_per_day"] * g["petrol_ngn_l"] * 365 + g["maintenance_ngn_month"] * 12)
    pc = g["freezer_ngn"] + g["generator_ngn"]
    t = g["generator_life_yr"]
    while t < n:
        pc += g["generator_ngn"] * df(t)
        t += g["generator_life_yr"]
    pc += yearly * sum(df(y) for y in range(1, n + 1))
    crf = r / (1 - (1 + r) ** -n)
    return pc * crf / 365, yearly / 365


# ======================================================================
# 3. REPORT
# ======================================================================
def m_(x):
    return f"{x/1e6:,.2f}M"


def row(label, d):
    return (f"  {label:41s} {d['bat_kwh']:5.1f} kWh  {d['pcm_kg']:5.0f} kg ({d['pcm_l']:3.0f} L)  "
            f"{d['pv_kwp']*1000:5.0f} W PV  {d['need_w']:4.0f} W comp  upfront {m_(d['upfront']):>7}  "
            f"10-yr {m_(d['total']):>7}  N{d['per_day']:,.0f}/day")


def report(a=A):
    out = []
    p = out.append
    for mode in a["modes"]:
        m = a["modes"][mode]
        load, walls, restock = daily_load_kwh(a, m)
        _, night, auto = stores(a, m)
        t_evap, dk, ok = pcm_evap(a, m)
        p("=" * 112)
        p(f"{m['label']}  |  PCM: {m['pcm']['name']}, melts at {m['pcm']['t_melt']} °C")
        p("=" * 112)
        p(f"Cooling load {load:.2f} kWh/day ({load*1000/24:.0f} W average): walls and lid {walls:.2f}, restocking {restock:.2f}")
        p(f"Storage needed: nightly {night:.2f} kWh (no sun for {24-a['sun_hours']:.0f} h), "
          f"cloudy-day reserve {auto:.2f} kWh ({a['autonomy_days']:.0f} days)")
        p(f"Refreezing the PCM needs an evaporator at {t_evap:.1f} °C, {dk:.1f} K below normal: "
          f"COP {m['cop_normal']:.2f} -> {m['cop_normal']*(1-a['cop_slope']*dk):.2f}")
        p("\n  DESIGNS                                   battery    PCM              solar     compressor  costs")
        for label, fn, fa in NAMED:
            d = design(a, mode, fn, fa)
            p(row(label, d))
        b = best(a, mode)
        p(row(f"Cheapest mix (PCM: {b['f_night']:.0%} night, {b['f_auto']:.0%} cloudy)", b))
        p("\n  Where the 10-year cost goes (present value, N millions)")
        keys = ["freezer", "solar", "battery", "PCM + panels", "bigger cabinet", "extra compressor", "upkeep"]
        p("  " + " " * 41 + "".join(f"{k:>12s}" for k in ["freezer", "solar", "battery", "PCM", "cabinet", "compressor", "upkeep"]))
        for label, fn, fa in NAMED:
            d = design(a, mode, fn, fa)
            p(f"  {label:41s}" + "".join(f"{d['pc'][k]/1e6:12.2f}" for k in keys))

        p("\n  SUPERCOOLING: what your lab problem costs here (design: battery for nights, PCM for cloudy days)")
        for sc in [0, 2, 4, 6, 8, 10, 13]:
            t_e, dk_, ok_ = pcm_evap(a, m, sc)
            if not ok_:
                p(f"    {sc:2d} K: evaporator would need {t_e:.0f} °C, below the compressor's {a['t_evap_min']:.0f} °C limit -> PCM cannot refreeze")
                continue
            d = design(a, mode, 0.0, 1.0, sc)
            p(f"    {sc:2d} K: evaporator {t_e:5.1f} °C, COP {d['cop_p']:.2f}, compressor {d['need_w']:.0f} W, "
              f"10-yr {m_(d['total'])}, N{d['per_day']:,.0f}/day")
        p("")

    # sensitivity on the freezer
    p("=" * 112)
    p("SENSITIVITY (freezer): cheapest mix and its cost per day, one input changed at a time")
    p("=" * 112)
    base = best(a, "freezer")
    p(f"  {'Base case':46s} PCM {base['f_night']:.0%} night / {base['f_auto']:.0%} cloudy   N{base['per_day']:,.0f}/day")
    tests = [
        ("Battery price N100k / N300k per kWh", "battery_ngn_per_kwh", (100_000, 300_000)),
        ("Compressor capacity N2,000 / N8,000 per W", "compressor_ngn_per_w", (2000, 8000)),
        ("PCM material N150 / N1,500 per kg", None, (150, 1500)),
        ("Cloudy-day reserve 1 / 5 days", "autonomy_days", (1.0, 5.0)),
        ("Rainy-season yield 3.5 / 5.3 kWh/kWp/day", "pv_yield_worst", (3.5, 5.3)),
        ("Battery life 4 / 12 years", "battery_calendar_yr", (4.0, 12.0)),
        ("Discount rate 6% / 20%", "discount_real", (0.06, 0.20)),
        ("Sun hours for the compressor 5 / 9", "sun_hours", (5.0, 9.0)),
        ("Days to rebuild the reserve 2 / 8", "recovery_days", (2.0, 8.0)),
    ]
    for label, key, (lo, hi) in tests:
        res = []
        for v in (lo, hi):
            b = copy.deepcopy(a)
            if key is None:
                b["modes"]["freezer"]["pcm"]["material_ngn_kg"] = v
            else:
                b[key] = v
            d = best(b, "freezer")
            res.append(f"PCM {d['f_night']:.0%}/{d['f_auto']:.0%} N{d['per_day']:,.0f}")
        p(f"  {label:46s} {res[0]:>22s}  |  {res[1]:>22s}")

    gen_day, fuel_day = generator_benchmark(a)
    p("\n" + "=" * 112)
    p(f"BENCHMARK: AC chest freezer on a petrol generator {a['gen']['hours_per_day']:.0f} h/day: "
      f"N{gen_day:,.0f}/day all-in (fuel and upkeep alone N{fuel_day:,.0f}/day)")
    p(f"Cheapest solar freezer: N{base['per_day']:,.0f}/day, about {gen_day/base['per_day']:.1f}x cheaper over 10 years")
    p("\nCAN A TRADER AFFORD THE UPFRONT COST? (cheapest solar freezer, paid off over 24 months)")
    for label, rate in [("Commercial bank rate 31%/yr", 0.31), ("Concessional 14%/yr", 0.14)]:
        r = rate / 12
        pmt = base["upfront"] * r / (1 - (1 + r) ** -24)
        p(f"  {label:30s} N{pmt:,.0f}/month   vs generator fuel and upkeep N{fuel_day*365/12:,.0f}/month")
    print("\n".join(out))


if __name__ == "__main__":
    report()
