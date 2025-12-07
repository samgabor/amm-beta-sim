#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ANVIL_PORT=8545
RPC_URL="http://127.0.0.1:${ANVIL_PORT}"
PK_DEFAULT="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

# Positional args: alpha, beta, steps, ranges volatility, rangewidth, rangsep
ALPHA="${1:-2.0}"
BETA="${2:-5.0}"
STEPS="${3:-20}"
RANGES="${4:-10}"
VOLATILITY="${5:-0.01}"
RANGEWIDTH="${6:-120}"
RANGSEP="${7:-180}"



echo "=== FULL RUN PIPELINE START ==="
echo "[*] Using Beta parameters: alpha=${ALPHA}, beta=${BETA}"
echo "[*] Simulation steps: ${STEPS}"
echo "[*] Liquidity ranges: ${RANGES}"
echo "[*] Volatility: ${VOLATILITY}"
echo "[*] Range width: ${RANGEWIDTH}"
echo "[*] Inter-range separation: ${RANGSEP}" 

# 1) Kill existing anvil if any
if pgrep -x anvil >/dev/null 2>&1; then
  echo "[*] Killing existing anvil..."
  pkill anvil || true
  sleep 1
fi

# 2) Start fresh anvil
echo "[*] Starting anvil on port ${ANVIL_PORT}..."
cd "$PROJECT_ROOT"
# --block-time 1
anvil  --disable-code-size-limit --port "${ANVIL_PORT}"  > /tmp/anvil.log 2>&1 &
ANVIL_PID=$!
echo "[*] Anvil PID: ${ANVIL_PID}"
# give anvil a moment to start
sleep 2

# 3) Bootstrap all on-chain contracts and write addresses.json
echo "[*] Running BootstrapAll.s.sol..."
cd "$PROJECT_ROOT/onchain"

export DEPLOYER_PRIVATE_KEY="${PK_DEFAULT}"

forge script script/BootstrapAll.s.sol:BootstrapAll \
  --rpc-url "${RPC_URL}" \
  --broadcast --skip-simulation --code-size-limit 65536

# 4) Generate Beta ranges JSON off-chain
echo "[*] Generating Beta ranges (alpha=${ALPHA}, beta=${BETA}, ranges=${RANGES}, range_width=${RANGEWIDTH}, inter_range_separation=${RANGSEP})..."
cd "$PROJECT_ROOT/offchain"

uv run python generate_beta_ranges.py \
  --alpha "${ALPHA}" \
  --beta "${BETA}" \
  --ranges "${RANGES}" \
  --range-width "${RANGEWIDTH}" \
  --inter-range-separation "${RANGSEP}"  


# 5) Deploy Beta LP position on-chain
echo "[*] Deploying Beta LP ranges..."
cd "$PROJECT_ROOT/onchain"

forge script script/DeployBetaLP.s.sol:DeployBetaLP \
  --rpc-url "${RPC_URL}" \
  --broadcast --skip-simulation

# 6) Run orderflow simulation off-chain
echo "[*] Running orderflow simulation..."
cd "$PROJECT_ROOT/offchain"

uv run python run_orderflow.py --steps "${STEPS}" --volatility "${VOLATILITY}" 
uv run python summarize_episode.py \
  --num-steps "${STEPS}" \
  --alpha "${ALPHA}" \
  --beta "${BETA}" \
  --num-ranges "${RANGES}" \
  --range-width "${RANGEWIDTH}" \
  --range-sep "${RANGSEP}" \
  --volatility "${VOLATILITY}" \
  --path "episode.csv" \
  --summary-out "summary.csv"

echo "=== FULL RUN PIPELINE COMPLETE ==="

echo "[*] Stopping anvil (PID: ${ANVIL_PID})..."
kill "${ANVIL_PID}" 2>/dev/null || true