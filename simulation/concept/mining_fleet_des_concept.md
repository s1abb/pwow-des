# Mining Fleet Availability Simulator
## Discrete Event Simulation with Python SimPy — Concept Document

---

## 1. What the Model Does

This model simulates a fleet of large surface mining haul trucks and hydraulic mining shovels to estimate **physical availability (PA%)** under different maintenance strategies and resource constraints.

Each machine does one of three things at any point in time:

- **Operating** — running and accumulating machine hours
- **Scheduled PM or overhaul** — undergoing planned maintenance
- **Unscheduled repair** — broken down and under repair

Trucks and shovels are modelled as **independent equipment classes**. Trucks do not depend on shovel availability — the model does not simulate production interactions between equipment. It is purely a **maintenance and availability model**.

The two equipment types share workshop bays and mechanics as common resources. This is where they interact in the simulation: a shovel occupying a bay for a major overhaul reduces the bays available to trucks, and vice versa.

---

## 2. Why Not Excel?

Excel can calculate an average availability figure. It cannot explain *why* that number is what it is, or what happens when things go wrong simultaneously.

The key things SimPy does that Excel fundamentally cannot:

**Queuing.** If three trucks break down while a shovel is also in for a major overhaul and there are only four workshop bays, something queues. That wait time is lost availability. Excel assumes infinite capacity or requires the user to pre-calculate contention — SimPy models it automatically.

**Stochastic failure interaction.** Each machine has multiple components, each with its own failure clock. The first to fail wins. The resulting queue, backlog, and mechanic utilisation emerge from the simulation rather than being assumed as inputs.

**Mixed resource demand.** Trucks require a workshop bay for every maintenance event. Shovels only need a bay for major events — minor PMs are done on-site and consume only a mechanic. This asymmetric bay demand cannot be represented cleanly in a spreadsheet but is trivial in SimPy.

---

## 3. The Core Loop

Both trucks and shovels run the same basic process continuously throughout the simulation. The only difference is whether a given maintenance event requires a workshop bay.

```
┌──────────────────────────────────────┐
│            OPERATING                 │
│   (hours accumulate on run clock)    │
└──────┬───────────────────────┬───────┘
       │                       │
  PM clock hits            Premature failure fires
  threshold                (Weibull draw)
       │                       │
       ▼                       ▼
┌──────────────────────────────┐   ┌──────────────────────────┐
│       SCHEDULED EVENT        │   │    UNSCHEDULED REPAIR    │
│                              │   │                          │
│  Shovel minor PM             │   │  All machines:           │
│    → mechanic only           │   │    bay + mechanic        │
│                              │   │                          │
│  Truck PM / any overhaul     │   │                          │
│    → bay + mechanic          │   │                          │
└──────────────┬───────────────┘   └──────────┬───────────────┘
               │                              │
               └──────────────┬───────────────┘
                              │
                       Back to OPERATING
```

Each machine maintains a **single PM clock** tracking cumulative operating hours. Multiple thresholds sit on this clock — routine PMs and major overhauls — and the next upcoming threshold determines when the machine next enters a scheduled event. After each event the clock continues from where it left off (it is not reset unless an overhaul interval restarts the component life).

**Opportunistic maintenance:** If a premature failure occurs within a configurable window of the next scheduled PM or overhaul threshold, both events are performed together, avoiding a separate future planned downtime.

---

## 4. Resources

Two shared resource pools drive all queuing behaviour in the model:

| Resource | SimPy Type | Used By | Notes |
|---|---|---|---|
| Workshop bays | `simpy.Resource` | Trucks — all events · Shovels — major events only | Queue forms when all bays occupied |
| Mechanics | `simpy.Resource` | All events across both equipment types | Single pool; capacity varies by shift |

A mechanic is always required for any maintenance event. A bay is required for all truck events and for shovel major overhauls and unscheduled repairs only. Shovel minor PMs consume only a mechanic.

When all bays or all mechanics are busy, arriving machines queue and wait. Queue time counts as downtime and directly reduces PA%.

Mechanic availability changes by shift. A day/afternoon/night roster can be applied so the model reflects real crew availability rather than assuming 24/7 cover.

---

## 5. Failure Modelling

### What the Weibull Models — Premature Failures Only

The Weibull distribution models **premature component failures** — events that occur *before* the component's scheduled overhaul threshold is reached. A well-maintained fleet will see most machines reach their scheduled overhaul cleanly; the Weibull captures the minority that fail early due to contamination, overloading, latent defects, or bad luck.

This is distinct from the scheduled overhaul itself, which is a planned PM event triggered by an hour threshold (see Section 6).

The shape parameter (β) determines how failure rate changes with age:

| β | Failure behaviour | Typical cause |
|---|---|---|
| < 1 | Decreasing rate — infant mortality | Early-life defects, installation errors |
| = 1 | Constant rate — random failures | External events, random stress |
| > 1 | Increasing rate — wear-out | Fatigue, erosion, progressive degradation |

Premature failure scale values are set below the scheduled overhaul interval so that most machines (>60%) reach their overhaul without a premature failure on any given component. Adjusting scale values downward simulates an ageing or poorly maintained fleet.

All premature failures — truck and shovel — require a bay and a mechanic.

### Truck Premature Failure Parameters

| Component | Scheduled Overhaul (hrs) | Premature Failure Scale (hrs) | Shape (β) | Failure Type |
|---|---|---|---|---|
| Engine | 20,000 | 12,000 | 2.0 | Contamination, overheating |
| Transmission | 13,000 | 8,000 | 1.8 | Progressive wear, shock loads |
| Injectors | 6,000 | 4,000 | 2.0 | Fuel contamination |
| Hydraulics | 4,000 | 2,500 | 1.5 | Mixed random / wear |
| Suspension | 3,000 | 2,000 | 2.0 | Overload events |
| Tyres | 5,000 | 3,000 | 2.5 | Blowouts, cuts, impact damage |

### Shovel Premature Failure Parameters

| Component | Scheduled Overhaul (hrs) | Premature Failure Scale (hrs) | Shape (β) | Failure Type |
|---|---|---|---|---|
| Engine | 20,000 | 12,000 | 2.0 | Contamination, overheating |
| Hydraulic pumps | 4,000 | 2,500 | 1.5 | Mixed random / wear |
| Swing ring / slew bearing | 6,000 | 4,000 | 2.0 | Progressive wear |
| Boom / stick pins | 3,000 | 2,000 | 2.2 | Wear, corrosion |
| GET / bucket teeth | 1,000 | 600 | 1.8 | Abrasive wear, impact |
| Undercarriage | 8,000 | 5,000 | 2.5 | Wear-out |

---

## 6. Maintenance Schedules

All scheduled events are triggered by hour thresholds on each machine's run clock. The `bay` flag determines whether a workshop bay must be requested in addition to a mechanic.

### 6.1 Haul Trucks

Based on CAT 793D and Komatsu 830E/930E OEM documentation and practitioner data. Every truck event — scheduled or unscheduled — requires a bay and a mechanic (`bay: True` throughout).

| Event | Interval (hrs) | Duration mean (hrs) | Duration SD (hrs) | Bay | Key Tasks |
|---|---|---|---|---|---|
| PM-A | 250 | 4 | 1.0 | Yes | Oil & filter change, lube, inspection walkover |
| PM-B | 500 | 8 | 1.5 | Yes | Fluid changes, cooling system sample |
| PM-C | 1,000 | 16 | 2.0 | Yes | Hydraulic service, major adjustments |
| PM-D | 3,000 | 32 | 4.0 | Yes | Valve adjustments, injector condition check |
| Suspension overhaul | 3,000 | 6 | 1.5 | Yes | Strut rebuild, nitrogen recharge |
| Hydraulic pump overhaul | 4,000 | 12 | 3.0 | Yes | Pump rebuild or replacement |
| Tyre replacement | 5,000 | 3 | 0.5 | Yes | Scheduled changeout ($40K–$70K/tyre) |
| Injector replacement | 6,000 | 8 | 2.0 | Yes | Full injector set replacement |
| Transmission overhaul | 13,000 | 48 | 8.0 | Yes | Transmission and final drive rebuild |
| Engine rebuild | 20,000 | 240 | 24 | Yes | Full overhaul (~$400K); 3+ per truck life |

> 250 hours ≈ every two weeks in a continuous 24/7 operation (~7,000 SMU/year).

### 6.2 Hydraulic Mining Shovels

Based on Cat 6040/6060 OEM documentation. Minor PMs are performed on-site at the machine using the ground-level service station — they require only a mechanic. Major overhauls and all unscheduled repairs require a bay and a mechanic.

| Event | Interval (hrs) | Duration mean (hrs) | Duration SD (hrs) | Bay | Key Tasks |
|---|---|---|---|---|---|
| Daily inspection | 10 | 0.5 | 0.2 | No | Walk-around, fluid levels, GET condition check |
| PM-A | 250 | 3 | 0.8 | No | Engine oil & filter, lube points, filter check |
| PM-B | 1,000 | 6 | 1.5 | No | Full fluid changes, hydraulic filter, cooling sample |
| GET / bucket teeth | 1,000 | 4 | 1.0 | No | On-machine tooth and shroud changeout |
| Boom / stick pin service | 3,000 | 8 | 2.0 | No | Pin inspection, re-grease, bushing check |
| Hydraulic pump overhaul | 4,000 | 16 | 4.0 | Yes | Pump rebuild or exchange |
| Swing ring overhaul | 6,000 | 24 | 6.0 | Yes | Bearing inspection, repack or replace |
| Undercarriage overhaul | 8,000 | 48 | 10.0 | Yes | Track, sprocket, roller rebuild |
| Swing gear overhaul | 12,000 | 32 | 8.0 | Yes | Gearbox rebuild |
| Engine rebuild | 20,000 | 240 | 24 | Yes | Full overhaul; 3+ per shovel life |

> Cat 6040/6060 engine oil change: 500 hrs standard, optional extension to 1,000 hrs. Shovel PM-B is modelled at the 1,000 hr interval using the extended option.

---

## 7. Model Parameters (SimPy-Ready)

The four dictionaries below share an identical key structure. The `bay` flag drives resource allocation logic — a value of `True` means the process must request both a bay and a mechanic before proceeding; `False` means only a mechanic is requested.

```python
# ── TRUCK: Scheduled PM & Overhaul ───────────────────────────────────────────
TRUCK_PM_SCHEDULE = {
    "PM_A":            {"interval": 250,    "duration_mean": 4,   "duration_sd": 1.0,  "bay": True},
    "PM_B":            {"interval": 500,    "duration_mean": 8,   "duration_sd": 1.5,  "bay": True},
    "PM_C":            {"interval": 1_000,  "duration_mean": 16,  "duration_sd": 2.0,  "bay": True},
    "PM_D":            {"interval": 3_000,  "duration_mean": 32,  "duration_sd": 4.0,  "bay": True},
    "suspension_OH":   {"interval": 3_000,  "duration_mean": 6,   "duration_sd": 1.5,  "bay": True},
    "hydraulic_OH":    {"interval": 4_000,  "duration_mean": 12,  "duration_sd": 3.0,  "bay": True},
    "tyre_replace":    {"interval": 5_000,  "duration_mean": 3,   "duration_sd": 0.5,  "bay": True},
    "injector_OH":     {"interval": 6_000,  "duration_mean": 8,   "duration_sd": 2.0,  "bay": True},
    "transmission_OH": {"interval": 13_000, "duration_mean": 48,  "duration_sd": 8.0,  "bay": True},
    "engine_rebuild":  {"interval": 20_000, "duration_mean": 240, "duration_sd": 24,   "bay": True},
}

# ── TRUCK: Premature Failures — Weibull(shape, scale) ────────────────────────
TRUCK_PREMATURE_FAILURE = {
    "engine":       {"shape": 2.0, "scale": 12_000, "repair_mean": 240, "repair_sd": 24,  "bay": True},
    "transmission": {"shape": 1.8, "scale":  8_000, "repair_mean": 48,  "repair_sd": 8,   "bay": True},
    "injectors":    {"shape": 2.0, "scale":  4_000, "repair_mean": 8,   "repair_sd": 2,   "bay": True},
    "hydraulics":   {"shape": 1.5, "scale":  2_500, "repair_mean": 12,  "repair_sd": 3,   "bay": True},
    "suspension":   {"shape": 2.0, "scale":  2_000, "repair_mean": 6,   "repair_sd": 1.5, "bay": True},
    "tyres":        {"shape": 2.5, "scale":  3_000, "repair_mean": 3,   "repair_sd": 0.5, "bay": True},
}

# ── SHOVEL: Scheduled PM & Overhaul ──────────────────────────────────────────
# bay: False → mechanic only (on-site)
# bay: True  → bay + mechanic (workshop)
SHOVEL_PM_SCHEDULE = {
    "daily_inspect":    {"interval": 10,     "duration_mean": 0.5, "duration_sd": 0.2,  "bay": False},
    "PM_A":             {"interval": 250,    "duration_mean": 3,   "duration_sd": 0.8,  "bay": False},
    "PM_B":             {"interval": 1_000,  "duration_mean": 6,   "duration_sd": 1.5,  "bay": False},
    "GET_replace":      {"interval": 1_000,  "duration_mean": 4,   "duration_sd": 1.0,  "bay": False},
    "pin_service":      {"interval": 3_000,  "duration_mean": 8,   "duration_sd": 2.0,  "bay": False},
    "hydraulic_OH":     {"interval": 4_000,  "duration_mean": 16,  "duration_sd": 4.0,  "bay": True},
    "swing_ring_OH":    {"interval": 6_000,  "duration_mean": 24,  "duration_sd": 6.0,  "bay": True},
    "undercarriage_OH": {"interval": 8_000,  "duration_mean": 48,  "duration_sd": 10.0, "bay": True},
    "swing_gear_OH":    {"interval": 12_000, "duration_mean": 32,  "duration_sd": 8.0,  "bay": True},
    "engine_rebuild":   {"interval": 20_000, "duration_mean": 240, "duration_sd": 24,   "bay": True},
}

# ── SHOVEL: Premature Failures — Weibull(shape, scale) ───────────────────────
SHOVEL_PREMATURE_FAILURE = {
    "engine":        {"shape": 2.0, "scale":  4_000, "repair_mean": 48,  "repair_sd": 24,  "bay": True},
    "hydraulics":    {"shape": 1.5, "scale":  2_500, "repair_mean": 16,  "repair_sd": 4,   "bay": True},
    "swing_ring":    {"shape": 2.0, "scale":  4_000, "repair_mean": 48,  "repair_sd": 12,  "bay": True},
    "boom_pins":     {"shape": 2.2, "scale":  2_000, "repair_mean": 12,  "repair_sd": 3,   "bay": True},
    "GET":           {"shape": 1.8, "scale":    600,  "repair_mean": 4,   "repair_sd": 1,   "bay": True},
    "undercarriage": {"shape": 2.5, "scale":  5_000, "repair_mean": 24,  "repair_sd": 6,   "bay": True},
}

# ── Shared Resources ──────────────────────────────────────────────────────────
N_BAYS      = 4   # workshop bays (all truck events; shovel major events only)
N_MECHANICS = 6   # mechanics — single pool across all events (day shift)

# ── Fleet Size ────────────────────────────────────────────────────────────────
N_TRUCKS  = 15
N_SHOVELS = 3

# ── Opportunistic Maintenance Window ─────────────────────────────────────────
OPP_WINDOW_HRS = 50   # if a premature failure fires within this many hours of
                       # the next scheduled threshold, combine both events

# ── Simulation Settings ───────────────────────────────────────────────────────
SIM_DURATION = 8_760   # hours (1 year)
N_RUNS       = 500     # Monte Carlo replications
```

---

## 8. KPI Outputs

KPIs are reported separately for trucks and shovels, and as a combined fleet summary. All outputs are distributions across N simulation runs, not single-point estimates.

| KPI | Description |
|---|---|
| **Physical availability % (PA%)** | `operating_time / total_scheduled_time` — per machine and fleet mean |
| **PA% distribution** | P10 / P50 / P90 across all simulation runs |
| **MTBF** | Mean time between failures, per component per equipment type |
| **MTTR** | Mean time to repair, per event type |
| **Scheduled vs. unscheduled ratio** | Count and proportion of planned vs. breakdown events |
| **Workshop bay queue depth** | Average and peak number of machines waiting for a bay |
| **Mechanic utilisation %** | Fraction of available shift hours spent on active work |

---

## 9. Scenario Analysis

| Question | Parameter Changed |
|---|---|
| How many mechanics sustain 90% fleet PA? | Sweep `N_MECHANICS` 4 → 12 |
| How many bays minimise queue without over-investment? | Sweep `N_BAYS` 2 → 8 |
| Does shovel major maintenance crowd out truck repairs? | Compare bay queue depth: trucks-only vs. combined fleet |
| What is the worst-case monthly availability? | Read P10 of PA% distribution |
| What does extending truck PM-A from 250 to 300 hrs do? | Change `TRUCK_PM_SCHEDULE["PM_A"]["interval"]` |
| What does extending shovel PM-B from 500 to 1,000 hrs do? | Change `SHOVEL_PM_SCHEDULE["PM_B"]["interval"]` |
| Is a night-shift crew worth the cost? | Toggle mechanic availability to 24/7 |
| How does fleet ageing affect availability? | Reduce all `scale` values by 10–20% |

---

## 10. Implementation Phases

**Phase 1 — Single truck**
One truck, one bay, one mechanic. Validate that Weibull TTF draws produce realistic MTBF. Confirm PM scheduling fires at the correct thresholds. Check that PA% lands in the 92–94% benchmark range.

**Phase 2 — Truck fleet with resource contention**
Scale to N trucks. Add multiple bays and mechanics. Introduce shift-based mechanic availability. Observe queue formation and its effect on fleet PA%.

**Phase 3 — Add shovels**
Introduce shovel processes alongside trucks. Implement the `bay` flag logic — minor shovel PMs consume only a mechanic, major events consume a bay and mechanic. Observe whether shovel major overhauls create bay contention that degrades truck PA%.

**Phase 4 — Monte Carlo and reporting**
Wrap the simulation in a Monte Carlo loop. Collect PA% per run for both equipment types. Compute P10/P50/P90 distributions. Plot availability distributions and sensitivity to key parameters.

---

## 11. Industry Benchmarks

| Metric | Value | Source |
|---|---|---|
| Target PA% — haul trucks | 92–94% | World-class surface mines |
| Target PA% — hydraulic shovels | 90–92% | World-class surface mines |
| Planned maintenance window | 8–10% of scheduled time | Industry standard |
| Unplanned downtime allowance | <8% of scheduled time | Derived from PA% targets |
| Typical SMU per year | ~7,000 hrs | Continuous 24/7 operation |
| Truck engine rebuild cost | ~$400,000 | Parts + labour, large haul truck |
| Truck downtime cost | $5,000–$20,000 / hr | Lost production |
| Shovel unplanned failure cost | $1.5–$2.5M / day | Large copper mine |
| Cat 6040/6060 engine oil interval | 500–1,000 hrs | OEM, with optional extension kit |
| Cat electric rope shovel design life | 120,000 hrs | ~20 years continuous operation |
