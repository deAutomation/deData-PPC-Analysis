#!/usr/bin/env python3
# coding: utf-8
#
# Sync PPC masterdata snapshots from GCS into a local dir weekly.py can read.
#
#   python3 scripts/sync.py                     # latest 2 full runs -> ./_in
#   python3 scripts/sync.py --latest 4          # four runs (for trend/backfill)
#   python3 scripts/sync.py --include-csv       # also pull the flattened CSVs
#   python3 scripts/sync.py --dry-run           # show what would transfer
#
# The downloader uploads gzipped objects named
#   ppc/masterplans/json/{ts}-ppc-website-masterplan-data-{slug}.json.gz
# weekly.py now reads .json.gz directly, but this script decompresses anyway so
# ./_in stays greppable and diffable.
#
# Needs an authenticated gcloud (`gcloud auth login` or ADC). Read-only: no
# writes, no deletes, never touches the bucket.

import argparse
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

BUCKET = 'gs://masterplans'
JSON_PREFIX = 'ppc/masterplans/json/'
CSV_PREFIX = 'ppc/masterplans/csv/'
NAME = re.compile(r'/(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})-ppc-website-masterplan-data-(.+)\.json\.gz$')

BACKEND = 'auto'


def gcloud(args, capture=True):
    return subprocess.run(['gcloud', 'storage'] + args,
                          capture_output=capture, text=True, timeout=300)


def _py_client():
    """ADC or GOOGLE_APPLICATION_CREDENTIALS service-account JSON."""
    from google.cloud import storage
    return storage.Client()


def _py_list(prefix):
    c = _py_client()
    return [f'gs://masterplans/{b.name}'
            for b in c.list_blobs('masterplans', prefix=prefix)]


def _py_download(uri, local):
    from google.cloud import storage
    _, _, rest = uri.partition('gs://')
    bucket, _, blob = rest.partition('/')
    _py_client().bucket(bucket).blob(blob).download_to_filename(local)


def list_objects(prefix):
    """List gs:// URIs. gcloud first, then the Python client (ADC / SA key)."""
    global BACKEND
    if BACKEND in ('auto', 'gcloud'):
        r = gcloud(['ls', BUCKET + '/' + prefix])
        if r.returncode == 0:
            BACKEND = 'gcloud'
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        err = (r.stderr or '')
        if BACKEND == 'gcloud':
            sys.exit('gcloud failed: ' + (err.strip().splitlines() or ['?'])[-1])
        py_err = None
        try:
            BACKEND = 'python'
            return _py_list(prefix)
        except Exception as e:                      # noqa: BLE001
            py_err = f'{type(e).__name__}: {e}'
        if 'active account' in err:
            sys.exit('Not authenticated. Run: gcloud auth login '
                     '(or set GOOGLE_APPLICATION_CREDENTIALS to a service-account key)\n'
                     f'  python backend also failed: {py_err}')
        sys.exit(f'Cannot list {prefix}: {(err.strip().splitlines() or ["?"])[-1]}\n'
                 f'  python backend: {py_err}')
    BACKEND = 'python'
    return _py_list(prefix)


def download(uri, local):
    if BACKEND == 'python':
        _py_download(uri, local)
        return
    r = gcloud(['cp', uri, local])
    if r.returncode != 0:
        sys.exit(f'copy failed for {uri}: {(r.stderr or "").strip()}')


def runs_from(uris):
    """Group snapshot objects by run timestamp: {ts: {slug: uri}}."""
    runs = defaultdict(dict)
    for u in uris:
        m = NAME.search(u)
        if m:
            runs[m.group(1)][m.group(2)] = u
    return runs


def full_runs(runs, min_estates):
    return {t: v for t, v in runs.items() if len(v) >= min_estates}


def _decompress(src, dst):
    """Write plain text. The Python client may already have ungzipped it."""
    try:
        with gzip.open(src, 'rb') as fh:
            data = fh.read()
    except (gzip.BadGzipFile, OSError):
        with open(src, 'rb') as fh:
            data = fh.read()
    with open(dst, 'wb') as fh:
        fh.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dest', default='_in', help='local dir (default ./_in)')
    ap.add_argument('--latest', type=int, default=2, help='how many recent runs (default 2)')
    ap.add_argument('--min-estates', type=int, default=20, help='a "full" run floor (default 20)')
    ap.add_argument('--include-csv', action='store_true')
    ap.add_argument('--backend', choices=['auto', 'gcloud', 'python'], default='auto',
                    help='gcloud CLI, Python GCS client (ADC/SA key), or auto')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    global BACKEND
    BACKEND = args.backend

    runs = full_runs(runs_from(list_objects(JSON_PREFIX)), args.min_estates)
    if len(runs) < 2:
        sys.exit(f'need 2 full runs (>= {args.min_estates} estates) in {JSON_PREFIX}; '
                 f'found {len(runs)}')
    chosen = sorted(runs)[-args.latest:]
    print(f'{len(runs)} full runs in bucket; taking {len(chosen)}: '
          f'{", ".join(f"{t} ({len(runs[t])})" for t in chosen)}')

    os.makedirs(args.dest, exist_ok=True)
    pulled = skipped = 0
    for ts in chosen:
        for slug, uri in sorted(runs[ts].items()):
            target = os.path.join(args.dest, f'{ts}-ppc-website-masterplan-data-{slug}.json')
            if os.path.exists(target):
                skipped += 1
                continue
            if args.dry_run:
                print(f'  would fetch {slug} ({ts})')
                pulled += 1
                continue
            with tempfile.TemporaryDirectory() as tmp:
                local = os.path.join(tmp, 'obj.json.gz')
                download(uri, local)
                _decompress(local, target)
            pulled += 1
        if args.include_csv and not args.dry_run:
            for slug in sorted(runs[ts]):
                uri = f'{BUCKET}/{CSV_PREFIX}{ts}-ppc-website-masterplan-data-{slug}.csv.gz'
                target = os.path.join(args.dest, f'{ts}-ppc-website-masterplan-data-{slug}.csv')
                if os.path.exists(target):
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    local = os.path.join(tmp, 'obj.csv.gz')
                    download(uri, local)
                    _decompress(local, target)

    print(f'{"would pull" if args.dry_run else "pulled"} {pulled}, already present {skipped} -> {args.dest}/')
    if not args.dry_run and pulled:
        print(f'next: python3 scripts/weekly.py --input {args.dest}')


if __name__ == '__main__':
    main()
