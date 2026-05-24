"""
Sanity check both simulation runs before analysis.
Checks: completeness, error counts, agent integrity, physics validity.
"""
import pandas as pd
from pathlib import Path
import sys

BASELINE_TEL  = 'data/logs/telemetry/telemetry_sim-20260423-171550.csv'
BASELINE_EVT  = 'data/logs/telemetry/events_sim-20260423-171550.csv'
RL_TEL        = 'data/logs/telemetry/telemetry_sim-20260424-075140.csv'
RL_EVT        = 'data/logs/telemetry/events_sim-20260424-075140.csv'
BASELINE_LOG  = 'logs/sim_20260423_171550_sim-20260423-171550.log'
RL_LOG        = 'logs/sim_20260424_075140_sim-20260424-075140.log'

def check_log_errors(log_path, label):
    with open(log_path, encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    errors   = [l.strip() for l in lines if '- ERROR' in l or '- CRITICAL' in l]
    warnings = [l.strip() for l in lines if '- WARNING' in l]
    days     = [l for l in lines if 'Simulation time: Day' in l]
    print(f"\n{'='*60}")
    print(f"  LOG CHECK: {label}")
    print(f"{'='*60}")
    print(f"  Total log lines : {len(lines):,}")
    print(f"  Days logged     : {len(days)} (last: Day {len(days)})")
    print(f"  ERROR lines     : {len(errors)}")
    print(f"  WARNING lines   : {len(warnings)}")
    if errors:
        print("  ERRORS FOUND:")
        for e in errors[:5]:
            print(f"    {e}")
    else:
        print("  [OK] No errors or critical failures found")
    return len(errors) == 0, len(days)

def check_events(evt_path, tel_path, label):
    print(f"\n{'='*60}")
    print(f"  DATA CHECK: {label}")
    print(f"{'='*60}")

    evt = pd.read_csv(evt_path)
    tel = pd.read_csv(tel_path)

    print(f"  Event rows      : {len(evt):,}")
    print(f"  Telemetry rows  : {len(tel):,}")

    # Event type breakdown
    if 'type' in evt.columns:
        counts = evt['type'].value_counts()
        print(f"\n  Event breakdown:")
        for etype, cnt in counts.items():
            print(f"    {etype:35s}: {cnt:,}")

    # Time range check
    if 'time' in evt.columns:
        max_time = evt['time'].max()
        expected_min = 365 * 24 * 60  # 365 days in minutes
        pct = max_time / expected_min * 100
        print(f"\n  Time coverage   : {max_time:,.0f} min / {expected_min:,} min ({pct:.1f}%)")
        if pct >= 99:
            print("  [OK] Full 365 days covered")
        else:
            print(f"  [!!] Only {pct:.1f}% of 365 days — simulation may have been cut short!")

    # Truck count
    if 'truck_id' in tel.columns:
        trucks = tel['truck_id'].nunique()
        print(f"  Unique trucks   : {trucks}")

    # RSL sanity (should be 0-100)
    if 'cargo_rsl' in tel.columns:
        rsl = tel['cargo_rsl'].dropna()
        print(f"  RSL range       : {rsl.min():.1f}% – {rsl.max():.1f}%")
        bad_rsl = (rsl < 0).sum() + (rsl > 100).sum()
        if bad_rsl > 0:
            print(f"  [!!] {bad_rsl} out-of-range RSL values!")
        else:
            print("  [OK] RSL values in valid range")

    # Fuel sanity
    if 'fuel_level_L' in tel.columns:
        fuel = tel['fuel_level_L'].dropna()
        print(f"  Fuel range      : {fuel.min():.1f}L – {fuel.max():.1f}L")
        if fuel.min() < -1:
            print(f"  [!!] Negative fuel values found!")
        else:
            print("  [OK] Fuel values look valid")

    # Delivery count
    deliveries = len(evt[evt['type'] == 'delivery_complete']) if 'type' in evt.columns else 'N/A'
    print(f"  Total deliveries: {deliveries}")


if __name__ == '__main__':
    all_ok = True
    issues = []

    ok1, days1 = check_log_errors(BASELINE_LOG, "PHASE 1 - BASELINE (Heuristic)")
    ok2, days2 = check_log_errors(RL_LOG, "PHASE 2 - RL ENABLED (PPO)")

    if days1 != 365: issues.append(f"Baseline only logged {days1} days (expected 365)")
    if days2 != 365: issues.append(f"RL only logged {days2} days (expected 365)")

    check_events(BASELINE_EVT, BASELINE_TEL, "PHASE 1 - BASELINE")
    check_events(RL_EVT, RL_TEL, "PHASE 2 - RL ENABLED")

    print(f"\n{'='*60}")
    print("  OVERALL VERDICT")
    print(f"{'='*60}")
    if not issues and ok1 and ok2:
        print("  [OK] Both simulations look clean and complete.")
        print("  [OK] Ready to proceed with analysis.")
    else:
        print("  [!!] Issues found:")
        for i in issues:
            print(f"    - {i}")
