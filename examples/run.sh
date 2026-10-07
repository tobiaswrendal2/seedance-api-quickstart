#!/usr/bin/env bash
# Post any body in this folder, wait for the job and download it.
#   ./examples/run.sh examples/seedance-2.0-mini-draft.json logo.mp4
# Works for every Seedance model: the body's "model" field picks it.
set -euo pipefail
: "${SEEDANCE_API_KEY:?export SEEDANCE_API_KEY first}"
BODY=${1:?usage: run.sh BODY.json [OUTPUT.mp4]}
OUT=${2:-seedance.mp4}
API=${SEEDANCE_BASE_URL:-https://argolink.io/v1}
AUTH="Authorization: Bearer $SEEDANCE_API_KEY"

ID=$(curl -fsS "$API/videos/generations" -H "$AUTH" -H "Content-Type: application/json" -d @"$BODY" | jq -er .request_id)
echo "submitted $ID ($(jq -r .model "$BODY"))" >&2

while :; do
  JOB=$(curl -fsS "$API/videos/$ID" -H "$AUTH")
  case $(jq -r .status <<<"$JOB") in
    done) break ;;
    failed | expired) jq . <<<"$JOB" >&2; exit 1 ;;
    *) echo "  $(jq -r '.progress // 0' <<<"$JOB")%" >&2; sleep 12 ;;
  esac
done

curl -fsSL "$API/videos/$ID/content" -H "$AUTH" -o "$OUT"
echo "saved $OUT, billed $(jq -r .usage.billed_seconds <<<"$JOB") s"
