#!/usr/bin/env bash
# Full-fleet LCOH vs availability sweep on a fresh EC2 checkout.
#
#   bash scripts/ec2_fleet_sweep.sh --fresh            # first run: back up any old per-site results, then sweep
#   bash scripts/ec2_fleet_sweep.sh                    # resume after an interruption (keeps finished sites)
#   bash scripts/ec2_fleet_sweep.sh --fresh --km "15"  # one radius only
#   bash scripts/ec2_fleet_sweep.sh --fresh --hybrid ...   # hybrid low-temperature supply, results tagged _hybrid
#   bash scripts/ec2_fleet_sweep.sh --fresh --s3 s3://annaiecc/facility_IHB_potential/results/<run> --stop-when-done
#        # upload results to S3 when done (size-checked), then stop the instance. The stop also
#        # happens if the sweep fails, after uploading whatever results exist. The disk is kept.
#
# Runs the 5 km and then the 15 km sweep (2,192 sites x 10 availability floors each) with the
# committed solver settings (linked 8,760-h year, interior point, discharge capped at load).
# Per-site results: outputs/multiband/analysis/lcoh_vs_availability_<id>_<km>km.csv
# Logs: logs/fleet_sweep_<km>km.log. Start it under nohup or tmux, it runs for many hours.
set -euo pipefail
cd "$(dirname "$0")/.."

FRESH=0
KMS="5 15"
WORKERS="${WORKERS:-}"
S3_PREFIX=""
STOP=0
SFX=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fresh) FRESH=1; shift ;;
    --km) KMS="$2"; shift 2 ;;
    --workers) WORKERS="$2"; shift 2 ;;
    --s3) S3_PREFIX="${2%/}"; shift 2 ;;
    --stop-when-done) STOP=1; shift ;;
    --hybrid) export HYBRID_LOW_TEMP=1 SWEEP_TAG=hybrid; SFX="_hybrid"; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done

finalize() {
  status=$?
  mkdir -p logs
  if [[ -n "$S3_PREFIX" ]]; then
    tarball="sweep_results_$(date -u +%Y%m%dT%H%MZ)_$(git rev-parse --short HEAD).tar.gz"
    { ls outputs/multiband/analysis | grep -E "^lcoh_vs_availability_[0-9]+_(5|15)km${SFX}\.csv\$|^fleet_availability_(sweep|knee)_(5|15)km${SFX}|^hp_cost_breakeven" \
        | sed 's|^|outputs/multiband/analysis/|'; ls logs/*.log; } > /tmp/sweep_files.txt 2>/dev/null || true
    if tar -czf "$HOME/$tarball" -T /tmp/sweep_files.txt \
       && aws s3 cp --only-show-errors "$HOME/$tarball" "$S3_PREFIX/$tarball"; then
      local_bytes=$(stat -c %s "$HOME/$tarball")
      remote_bytes=$(aws s3 ls "$S3_PREFIX/$tarball" | awk '{print $3}')
      if [[ "$local_bytes" == "$remote_bytes" ]]; then
        echo "=== $(date -u +%FT%TZ) uploaded $S3_PREFIX/$tarball ($local_bytes bytes, verified)" | tee -a logs/finalize.log
      else
        echo "=== $(date -u +%FT%TZ) UPLOAD SIZE MISMATCH local $local_bytes remote $remote_bytes" | tee -a logs/finalize.log
      fi
      aws s3 cp --only-show-errors logs/finalize.log "$S3_PREFIX/finalize.log" || true
    else
      echo "=== $(date -u +%FT%TZ) UPLOAD FAILED, results stay on the instance disk" | tee -a logs/finalize.log
    fi
  fi
  echo "=== $(date -u +%FT%TZ) sweep script exit status $status" | tee -a logs/finalize.log
  if [[ "$STOP" == 1 ]]; then
    echo "=== stopping instance" | tee -a logs/finalize.log
    sudo shutdown -h +1  # instance shutdown behaviour is "stop": disk kept, billing stops
  fi
}
trap finalize EXIT

if [[ ! -x .venv/bin/python ]]; then
  # Current pandas/numpy need Python >= 3.11 (Amazon Linux 2023 ships 3.9: sudo dnf install python3.12)
  PY="${PYTHON:-$(command -v python3.12 || command -v python3.11 || echo python3)}"
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

# Solar hourly profiles live on S3 (needs an instance role or aws credentials with read access).
.venv/bin/python pull_s3_data.py

n=$(ls solar_radiation/outputs/hourly_profiles/*_2023.parquet | wc -l)
if [[ "$n" -lt 2192 ]]; then
  echo "only $n solar profiles present, expected >= 2192"; exit 1
fi

if [[ -z "$WORKERS" ]]; then
  WORKERS=$(nproc)
fi

mkdir -p logs
ANALYSIS=outputs/multiband/analysis
for km in $KMS; do
  if [[ "$FRESH" == 1 ]]; then
    # The sweep skips any site whose per-site CSV already has all floors, so stale results
    # from an earlier model version must not be left in place.
    old=$(find "$ANALYSIS" -maxdepth 1 -regextype posix-extended \
          -regex ".*/lcoh_vs_availability_[0-9]+_${km}km${SFX}\.csv" | wc -l)
    if [[ "$old" -gt 0 ]]; then
      bak="$ANALYSIS/_stale_$(date +%Y%m%d_%H%M%S)_${km}km"
      mkdir -p "$bak"
      find "$ANALYSIS" -maxdepth 1 -regextype posix-extended \
        -regex ".*/lcoh_vs_availability_[0-9]+_${km}km${SFX}\.csv" -exec mv {} "$bak"/ \;
      echo "moved $old old ${km} km per-site results to $bak"
    fi
  fi
  echo "=== $(date -u +%FT%TZ) start ${km} km sweep${SFX}, $WORKERS workers, commit $(git rev-parse --short HEAD)" | tee -a "logs/fleet_sweep_${km}km${SFX}.log"
  .venv/bin/python "$ANALYSIS/fleet_availability_sweep_${km}km.py" --max-workers "$WORKERS" 2>&1 | tee -a "logs/fleet_sweep_${km}km${SFX}.log"
  echo "=== $(date -u +%FT%TZ) finished ${km} km sweep" | tee -a "logs/fleet_sweep_${km}km${SFX}.log"
done
