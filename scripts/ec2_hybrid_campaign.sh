#!/usr/bin/env bash
# Break-even test, then the hybrid fleet sweep, then upload everything to S3 and stop the instance.
#
#   setsid nohup bash scripts/ec2_hybrid_campaign.sh s3://annaiecc/facility_IHB_potential/results/<run> \
#       > logs/campaign.log 2>&1 < /dev/null &
#
# The fleet launcher uploads its results (size-checked) and stops the instance when it ends, also on
# failure. If this script fails before the launcher starts, it stops the instance itself.
set -uo pipefail
cd "$(dirname "$0")/.."
P="${1%/}"
WORKERS="${WORKERS:-$(nproc)}"
LAUNCHED=0
trap '[[ $LAUNCHED == 0 ]] && { echo "=== campaign failed before fleet run, stopping"; sudo shutdown -h +1; }' EXIT
mkdir -p logs
echo "=== $(date -u +%FT%TZ) campaign start, commit $(git rev-parse --short HEAD), $WORKERS workers"

echo "=== $(date -u +%FT%TZ) break-even test"
.venv/bin/python outputs/multiband/analysis/hp_cost_breakeven.py --workers "$WORKERS" > logs/hp_cost_breakeven.log 2>&1
echo "    exit $?"
for f in outputs/multiband/analysis/hp_cost_breakeven.csv logs/hp_cost_breakeven.log; do
  [[ -f "$f" ]] && aws s3 cp --only-show-errors "$f" "$P/$(basename "$f")" && echo "    uploaded $P/$(basename "$f")"
done

echo "=== $(date -u +%FT%TZ) hybrid fleet sweep (uploads to $P and stops the instance when done)"
LAUNCHED=1
bash scripts/ec2_fleet_sweep.sh --fresh --hybrid --workers "$WORKERS" --s3 "$P" --stop-when-done
