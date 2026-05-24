"""
Full 365-day comparative analysis: Baseline vs RL-Enabled.
Reads event and telemetry CSVs and prints the final benchmark comparison.
"""
import pandas as pd
import json

import glob
import os

def get_latest_files():
    evt_files = sorted(glob.glob('data/logs/telemetry/events_sim-*.csv'), key=os.path.getmtime)
    tel_files = sorted(glob.glob('data/logs/telemetry/telemetry_sim-*.csv'), key=os.path.getmtime)
    
    if len(evt_files) < 2 or len(tel_files) < 2:
        raise ValueError("Not enough telemetry logs found! Need at least 2 runs to compare.")
    
    return evt_files[-2], evt_files[-1], tel_files[-2], tel_files[-1]

def analyze(evt_path, tel_path, label):
    print(f'\nLoading {label}...')
    df  = pd.read_csv(evt_path)
    tel = pd.read_csv(tel_path)

    evt_counts = df['event_type'].value_counts()

    # Parse delivery events
    deliveries = df[df['event_type'] == 'delivery_complete'].copy()
    d_parsed = []
    for _, row in deliveries.iterrows():
        try:
            d = json.loads(row['data'])
            d['_ts'] = row['timestamp']
            d_parsed.append(d)
        except Exception:
            pass
    del_df = pd.DataFrame(d_parsed) if d_parsed else pd.DataFrame()

    # Parse order events
    orders = df[df['event_type'] == 'order_placed'].copy()
    o_parsed = []
    for _, row in orders.iterrows():
        try:
            o_parsed.append(json.loads(row['data']))
        except Exception:
            pass
    ord_df = pd.DataFrame(o_parsed) if o_parsed else pd.DataFrame()

    total_orders     = len(ord_df)
    total_deliveries = len(del_df)
    service_level    = (total_deliveries / total_orders * 100) if total_orders > 0 else 0
    kg_delivered     = float(del_df['quantity_kg'].sum()) if 'quantity_kg' in del_df.columns else 0.0
    kg_ordered       = float(ord_df['quantity_kg'].sum()) if 'quantity_kg' in ord_df.columns else 0.0

    rsl_vals = del_df['avg_rsl_at_delivery'].dropna() if 'avg_rsl_at_delivery' in del_df.columns else pd.Series(dtype=float)
    avg_rsl_delivery = float(rsl_vals.mean()) if len(rsl_vals) > 0 else None

    truck_tel    = tel[tel['entity_type'] == 'truck']
    avg_fuel     = float(truck_tel['fuel'].mean()) if 'fuel' in truck_tel.columns else None
    avg_rsl_tel  = float(truck_tel['rsl'].mean())  if 'rsl'  in truck_tel.columns else None

    stockouts = int(evt_counts.get('inventory_shortage', 0))
    accidents = int(evt_counts.get('road_accident', 0))
    restocks  = int(evt_counts.get('warehouse_restock', 0))

    print(f'  Orders placed      : {total_orders:,}')
    print(f'  Orders delivered   : {total_deliveries:,}')
    print(f'  Service level      : {service_level:.1f}%')
    print(f'  Kg ordered         : {kg_ordered:,.0f} kg')
    print(f'  Kg delivered       : {kg_delivered:,.0f} kg')
    print(f'  Avg RSL (telemetry): {avg_rsl_tel:.1f}%' if avg_rsl_tel is not None else '  Avg RSL (tel)  : N/A')
    print(f'  Avg fuel level     : {avg_fuel:.1f}%'    if avg_fuel     is not None else '  Avg fuel       : N/A')
    print(f'  Stockouts          : {stockouts:,}')
    print(f'  Road accidents     : {accidents:,}')
    print(f'  Warehouse restocks : {restocks:,}')
    print(f'  Event breakdown:')
    for etype, cnt in evt_counts.items():
        print(f'    {etype:<38}: {cnt:,}')

    return {
        'label':        label,
        'orders':       total_orders,
        'deliveries':   total_deliveries,
        'service_pct':  service_level,
        'kg_ordered':   kg_ordered,
        'kg_delivered': kg_delivered,
        'avg_rsl_tel':  avg_rsl_delivery if avg_rsl_delivery is not None else avg_rsl_tel,
        'avg_fuel':     avg_fuel,
        'stockouts':    stockouts,
        'accidents':    accidents,
        'restocks':     restocks,
    }


def print_comparison(b, r):
    sep = '=' * 68
    print(f'\n\n{sep}')
    print('  FINAL OPTIMIZED BENCHMARK RESULTS: Baseline vs Final RL (PPO)')
    print(sep)
    col = 28
    print(f'  {"Metric":<{col}} {"Baseline":>12}  {"RL":>12}  {"Delta":>10}  Verdict')
    print(f'  {"-"*col} {"-"*12}  {"-"*12}  {"-"*10}  -------')

    metrics = [
        ('Service Level (%)',    'service_pct',  '%',   True),
        ('Orders Fulfilled',     'deliveries',   '',    True),
        ('Kg Delivered',         'kg_delivered', ' kg', True),
        ('Avg Cargo RSL (%)',    'avg_rsl_tel',  '%',   True),
        ('Avg Fuel Level (%)',   'avg_fuel',     '%',   True),
        ('Stockouts',            'stockouts',    '',    False),
        ('Road Accidents',       'accidents',    '',    False),
        ('Warehouse Restocks',   'restocks',     '',    True),
    ]

    improvements, regressions = 0, 0
    for name, key, unit, higher_better in metrics:
        bv = b.get(key)
        rv = r.get(key)
        if bv is None or rv is None:
            print(f'  {name:<{col}} {"N/A":>12}  {"N/A":>12}  {"N/A":>10}')
            continue
        delta   = rv - bv
        verdict = 'SAME'
        if delta != 0:
            if (delta > 0) == higher_better:
                verdict = 'BETTER'
                improvements += 1
            else:
                verdict = 'WORSE'
                regressions += 1
        bv_str = f'{bv:>11,.1f}{unit}'
        rv_str = f'{rv:>11,.1f}{unit}'
        d_str  = f'{delta:>+10,.1f}{unit}'
        print(f'  {name:<{col}} {bv_str}  {rv_str}  {d_str}  {verdict}')

    print(sep)
    print(f'  Improvements: {improvements}  |  Regressions: {regressions}')
    if improvements > regressions:
        print('  VERDICT: RL routing IMPROVES overall supply chain performance.')
    elif improvements == regressions:
        print('  VERDICT: RL routing shows MIXED results.')
    else:
        print('  VERDICT: RL routing does NOT improve performance at this training level.')
    print(sep)

    # Save to file
    out = 'data/analysis/benchmark_final_opt_results.txt'
    lines = []
    lines.append('FINAL OPTIMIZED BENCHMARK RESULTS: Baseline vs Final RL (PPO)')
    lines.append(sep)
    lines.append(f'{"Metric":<{col}} {"Baseline":>12}  {"RL":>12}  {"Delta":>10}  Verdict')
    for name, key, unit, higher_better in metrics:
        bv = b.get(key)
        rv = r.get(key)
        if bv is None or rv is None:
            lines.append(f'{name:<{col}} {"N/A":>12}  {"N/A":>12}  {"N/A":>10}')
            continue
        delta   = rv - bv
        verdict = ('BETTER' if (delta > 0) == higher_better else ('WORSE' if delta != 0 else 'SAME'))
        lines.append(f'{name:<{col}} {bv:>11,.1f}{unit}  {rv:>11,.1f}{unit}  {delta:>+10,.1f}{unit}  {verdict}')
    lines.append(sep)
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'\n  [SAVED] Results written to {out}')


if __name__ == '__main__':
    b_evt, r_evt, b_tel, r_tel = get_latest_files()
    print(f"Using Baseline Files: {b_evt}, {b_tel}")
    print(f"Using RL Files      : {r_evt}, {r_tel}")
    
    b = analyze(b_evt, b_tel, 'BASELINE (Heuristic A*)')
    r = analyze(r_evt, r_tel, 'RL-ENABLED (PPO)')
    print_comparison(b, r)
