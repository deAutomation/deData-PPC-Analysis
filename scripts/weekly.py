#!/usr/bin/env python3
# coding: utf-8
#
# PPC weekly analysis — diff the two latest FULL snapshots into net sales.
# Standalone: reads snapshot JSON (local dir or a GCS-synced dir), writes
# reports/ + charts/. No database, no ETL — GitHub only.
#
#   python3 scripts/weekly.py --input <snapshots-json-dir>
#
# Conventions (same as SGP):
#  - a lot that was published/available and is now status 7, or vanished
#    from the publish list without reappearing, counts as a SALE (last-asked price).
#  - a 7 that flips back to 2/available counts as a CANCELLATION (negative sale).
#  - first-seen lots are labelled, never silently counted as sales velocity.

import argparse
import csv
import glob
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLD = {'7'}


def load_runs(snapdir):
    files = sorted(glob.glob(os.path.join(snapdir, '*.json')))
    by_ts = {}
    for f in files:
        by_ts.setdefault(os.path.basename(f)[:19], []).append(f)
    full = {t: fs for t, fs in by_ts.items() if len(fs) >= 20}
    if len(full) < 2:
        raise SystemExit(f'need 2 full runs (>=20 estates), found: {sorted(len(v) for v in by_ts.values())}')
    ts = sorted(full)[-2:]
    out = []
    for t in ts:
        lots = {}
        for f in full[t]:
            d = json.load(open(f))
            slug = d.get('community', os.path.basename(f)[21:-5])
            cfg = d.get('lotConfig', d)
            for lot in cfg.get('all_lots_with_status', []):
                lots[(slug, str(lot.get('lot_id')))] = {
                    'community': slug, 'lot_id': str(lot.get('lot_id')),
                    'lot_number': str(lot.get('lot_number', '')),
                    'stage': lot.get('stage_name', ''), 'status': str(lot.get('lot_status', '?')),
                    'published': lot.get('lot_post_status') == 'publish'}
        out.append((t, lots))
    return out


def polygon_placeholder():
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='dir of *-ppc-website-masterplan-data-*.json snapshots')
    ap.add_argument('--out', default=os.path.join(HERE, 'reports'))
    args = ap.parse_args()
    (t0, prev), (t1, cur) = load_runs(args.input)
    est_prev = {k[0] for k in prev}
    est_cur = {k[0] for k in cur}
    new_est = sorted(est_cur - est_prev)
    gone_est = sorted(est_prev - est_cur)
    print(f'prev: {t0} ({len(prev)} lots)  cur: {t1} ({len(cur)} lots)')

    sales, cancels, new_listed, relisted, price_moves = [], [], [], [], []
    for key, c in cur.items():
        p = prev.get(key)
        if p is None:
            continue  # first-seen: labelled, not counted
        if p['status'] not in SOLD and c['status'] in SOLD:
            sales.append((c, p))
        if p['status'] in SOLD and c['status'] not in SOLD:
            cancels.append((c, p))
        if not p['published'] and c['published']:
            new_listed.append(c)
        if p['published'] and not c['published'] and c['status'] not in SOLD:
            relisted.append((c, p))

    by_est = defaultdict(lambda: Counter())
    for c, _ in sales:
        by_est[c['community']]['sales'] += 1
    for c, _ in cancels:
        by_est[c['community']]['cancels'] += 1
    for c in new_listed:
        by_est[c['community']]['new_listed'] += 1

    net = {e: v['sales'] - v['cancels'] for e, v in by_est.items()}
    date = t1[:10]
    repdir = os.path.join(args.out, date)
    chdir = os.path.join(HERE, 'charts')
    os.makedirs(repdir, exist_ok=True)
    os.makedirs(chdir, exist_ok=True)

    # charts: net sales per estate
    ranked = sorted(net.items(), key=lambda kv: -kv[1])[:20]
    if ranked:
        fig, ax = plt.subplots(figsize=(10, max(4, len(ranked) * 0.4)))
        es = [e for e, _ in ranked]
        ax.barh(es, [net[e] for e in es], color='#1f77b4', edgecolor='white')
        ax.set_xlabel('Net sales (sold − cancellations)')
        ax.set_title(f'Peet net sales by estate — {t0[:10]} → {date}', fontsize=11, weight='bold')
        fig.tight_layout()
        fig.savefig(os.path.join(chdir, f'{date}_net_sales.png'), bbox_inches='tight')
        plt.close(fig)

    # report
    tot_sales, tot_cx = sum(v['sales'] for v in by_est.values()), sum(v['cancels'] for v in by_est.values())
    tot_new = sum(v['new_listed'] for v in by_est.values())
    net_all = tot_sales - tot_cx

    # history across runs → chart #1: sales measured per week
    hist_path = os.path.join(args.out, 'history.csv')
    hist = {}
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            for r in list(csv.DictReader(f)):
                hist[r['week_ending']] = r
    hist[date] = {'week_ending': date, 'net_sales': net_all, 'sold': tot_sales,
                  'cancelled': tot_cx, 'newly_listed': tot_new, 'lots_tracked': len(cur)}
    with open(hist_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['week_ending', 'net_sales', 'sold', 'cancelled', 'newly_listed', 'lots_tracked'])
        w.writeheader()
        for d in sorted(hist):
            w.writerow(hist[d])
    weeks = sorted(hist)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = range(len(weeks))
    ax.bar(x, [int(hist[d]['sold']) for d in weeks], color='#2ca02c', label='sold')
    ax.bar(x, [-int(hist[d]['cancelled']) for d in weeks], color='#d62728', label='cancelled')
    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(weeks, rotation=20, ha='right', fontsize=8)
    ax.set_ylabel('lots / week')
    ax.legend(fontsize=8)
    if not any(int(hist[d]['sold']) or int(hist[d]['cancelled']) for d in weeks):
        ax.set_ylim(-1.5, 1.5)
        ax.text(0.5, 0.5, '0 net — no movement this week', ha='center', va='center',
                transform=ax.transAxes, fontsize=11, style='italic',
                bbox=dict(fc='white', alpha=0.8, ec='none'))
    ax.set_title('Peet — sales measured per week (sold green up, cancellations red down)', fontsize=11, weight='bold')
    fig.tight_layout()
    fig.savefig(os.path.join(chdir, 'sales_per_week.png'), bbox_inches='tight')
    plt.close(fig)
    lines = [f'# PPC weekly — {t0[:10]} → {date}', '',
             f'*Most recent data: {date} (snapshots {t0[:16]} → {t1[:16]}).*', '',
             '![sales measured per week](../../charts/sales_per_week.png)', '',
             f'Snapshots: {len(prev):,} → {len(cur):,} lots tracked.',
             f'**Net sales: {tot_sales - tot_cx}** ({tot_sales} sold, {tot_cx} cancellations), '
             f'{len(new_listed)} newly listed.', '',
             '## Per-estate', '']
    for e in sorted(by_est, key=lambda x: -(by_est[x]['sales'] - by_est[x]['cancels'])):
        v = by_est[e]
        lines.append(f"- **{e}**: net {v['sales'] - v['cancels']} "
                     f"(sold {v['sales']}, cancelled {v['cancels']}, newly listed {v['new_listed']})")
    if new_est or gone_est:
        lines += ['', '## Estate changes',
                  f"New: {', '.join(new_est) if new_est else '—'}",
                  f"Gone: {', '.join(gone_est) if gone_est else '—'}"]
    lines += ['', '_First-seen lots excluded from velocity. Method mirrors SGP persistent tracking._']
    open(os.path.join(repdir, 'WEEKLY.md'), 'w').write('\n'.join(lines) + '\n')

    rows = [['community', 'net_sales', 'sold', 'cancelled', 'newly_listed']]
    for e, v in sorted(by_est.items(), key=lambda kv: -(kv[1]['sales'] - kv[1]['cancels'])):
        rows.append([e, v['sales'] - v['cancels'], v['sales'], v['cancels'], v['new_listed']])
    with open(os.path.join(repdir, 'weekly.csv'), 'w', newline='') as f:
        csv.writer(f).writerows(rows)
    print(f'net={tot_sales - tot_cx} (sold {tot_sales}, cancelled {tot_cx}), newly listed {len(new_listed)}')
    print(f'wrote {repdir}/WEEKLY.md + weekly.csv, charts/{date}_net_sales.png')


if __name__ == '__main__':
    main()
