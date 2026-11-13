#!/usr/bin/env bash
# Download the Criteo Attribution Modeling for Bidding dataset (CC BY-NC-SA 4.0)
# from Criteo's official Hugging Face repository.
set -euo pipefail
DEST="${1:-data/raw}"
mkdir -p "$DEST"
URL="https://huggingface.co/datasets/criteo/criteo-attribution-dataset/resolve/main/criteo_attribution_dataset.tsv.gz"
if [ ! -f "$DEST/criteo_attribution_dataset.tsv.gz" ]; then
  curl -fSL -o "$DEST/criteo_attribution_dataset.tsv.gz" "$URL"
fi
echo "$DEST/criteo_attribution_dataset.tsv.gz"
