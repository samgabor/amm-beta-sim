# Uniswap v3 Beta Policy Simulation

This project simulates Uniswap v3-style LP allocation using **Beta-distributed liquidity ranges** around an ETH/USDC price, and an **Ornstein–Uuphi–Ornstein–Uhlenbeck (OU)** process for the “true” ETH price.

The stack:

- **Foundry** (`forge`, `anvil`) to deploy a **local fork** of Uniswap v3 (core + periphery) with mock WETH/USDC.
- **uv + Python** for:
  - Reading deployment artifacts
  - Generating Beta-based LP ranges
  - Simulating price paths
  - Computing P&L
  - Exporting CSV + JSON
  - Plotting LP ranges

---

## 1. Prerequisites

### 1.1 System Requirements

- Linux or Windows Subsystem for Linux (WSL)
- `git`
- `curl`

### 1.2 Install Foundry (Forge + Anvil)

```bash
curl -L https://foundry.paradigm.xyz | bash
source ~/.foundry/bin/foundryup
```

Verify:

```bash
forge --version
anvil --version
```

### 1.3 Install uv (Python environment manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Repository Structure

```
amm-beta-sim/
├── onchain/                       # All Solidity / Foundry / Uniswap v3 setup
│   ├── foundry.toml
│   ├── lib/                      # Installed dependencies
│   │   ├── v3-core/             # Uniswap v3 core contracts
│   │   ├── v3-periphery/        # Uniswap v3 periphery contracts
│   │   ├── openzeppelin-contracts/
│   │   ├── forge-std/
│   │   └── (other libs…)
│   │
│   ├── src/
│   │   ├── tokens/
│   │   │   ├── MockERC20.sol    # Mock ERC20 base
│   │   │   ├── WETH9.sol        # Wrapped ETH mock
│   │   │   └── USDCMock.sol     # USDC mock (6 decimals)
│   │   │
│   │   ├── LPHelper.sol         # Helper to mint multiple v3 ranges for LP
│   │   ├── SwapHelper.sol       # Helper to execute swaps against the pool
│   │   └── (other helpers/tests as needed)
│   │
│   ├── script/
│   │   ├── BootstrapAll.s.sol   # ONE script: deploy tokens, factory, pool, helpers
│   │   ├── DeployBetaLP.s.sol   # Reads beta_ranges.json, mints ranges via LPHelper
│   │   ├── addresses.json       # Auto-generated: all deployed contract addresses
│   │   └── beta_ranges.json     # Auto-generated: tickLowers, tickUppers, liquidity
│   │
│   └── broadcast/               # Forge broadcast logs (per network/anvil run)
│       └── (tx logs, receipts…)

├── offchain/                     # Python simulation + orchestration
│   ├── pyproject.toml            # uv / dependencies (web3, numpy, pandas, etc.)
│   ├── config.py                 # Original static config (may be older)
│   ├── config_dynamic.py         # Reads onchain/script/addresses.json, builds w3 + ADDRESSES
│   │
│   ├── abi/                      # ABI JSONs pulled from onchain build
│   │   ├── IUniswapV3Pool.json
│   │   ├── LPHelper.json
│   │   ├── SwapHelper.json
│   │   ├── MockERC20.json
│   │   └── (other ABIs as needed)
│   │
│   ├── beta_policy.py            # make_beta_ranges(): Beta-shaped symmetric tick ranges
│   ├── generate_beta_ranges.py   # Calls beta_policy + pool tick → writes beta_ranges.json
│   │
│   ├── sim_step.py               # Single-step swap via SwapHelper (on-chain call wrapper)
│   ├── state_snapshot.py         # Reads pool slot0, balances, and computes USDC/WETH
│   ├── valuation.py              # value_position_usdc() for LP & HODL values
│   ├── lp_fee_accounting.py      # LPFeeState + fee tracking & valuation
│   ├── price_process.py          # External ETH price process (mean-reverting, r, kappa, sigma)
│   │
│   ├── run_orderflow.py          # MAIN EPISODE SIM:
│   │                             #   - generates orderflow (buy/sell)
│   │                             #   - steps external market price
│   │                             #   - runs swaps via sim_step
│   │                             #   - (optionally) runs run_arbitrage_step
│   │                             #   - records LP + HODL values to episode.csv
│   │
│   ├── summarize_episode.py      # Reads episode.csv, prints summary & direction counts
│   ├── check_pool_state.py       # Diagnostic: prints slot0, price, liquidity
│   ├── inspect_price.py          # Convenience: prints current pool price & tick
│   ├── inspect_ranges.py         # Prints per-range tick bounds & implied USDC/WETH
│   └── (other small helper scripts added over time)
│
├── scripts/ 
│   │── full_run.sh               # End-to-end pipeline:
│                                 #   - start anvil
│                                 #   - forge script BootstrapAll.s.sol
│                                 #   - generate_beta_ranges.py (alpha/beta params)
│                                 #   - forge script DeployBetaLP.s.sol
│                                 #   - run_orderflow.py (N steps)
│                                 #   - summarize_episode.py
│                                 #   - stop anvil

```

---

## 3. Setup Instructions

### 3.1 Clone the project

```bash
git clone <repo-url> uniswap-v3-beta-sim
cd uniswap-v3-beta-sim
```

### 3.2 Install Solidity dependencies (if needed)

```bash
forge install uniswap/v3-core@v1.0.0
forge install uniswap/v3-periphery@v1.3.0
forge install OpenZeppelin/openzeppelin-contracts@v5.0.2
forge install OpenZeppelin/openzeppelin-contracts@v3.4.2-solc-0.7 --no-commit
forge install Uniswap/solidity-lib
forge install Brechtpd/base64
```

### 3.3 Install Python dependencies via uv

```bash
uv sync
```

---

## 4. Building and Deploying the Local Uniswap v3 Fork

### 4.1 Compile contracts

```bash
forge build
```

### 4.2 Start `anvil`

```bash
anvil --block-time 1 --gas-price 0
```

### 4.3 Export private key

```bash
export PRIVATE_KEY=0x<paste-key-from-anvil>
```

### 4.4 Deploy

```bash
forge script script/DeployUniswapV3.s.sol:DeployUniswapV3   --rpc-url http://127.0.0.1:8545   --private-key $PRIVATE_KEY   --broadcast -vv
```

---

## 5. Running the Simulation (Stable Mode)

```bash
uv run python/python/simulate_episode.py   --rpc-url http://127.0.0.1:8545   --deployment-file script-output/deployment.json   --eth-start 1   --usdc-start 1000   --alpha 1   --beta 1   --num-positions 3   --num-steps 5   --num-arbs 0   --rl-flag False   --eth-price0 3200   --price-band-pct 0.5   --epsilon 0.01   --episode-basename test   --ranges-json test_ranges.json   --csv-file test_episode.csv
```

Outputs:

- `test_ranges.json`
- `test_episode.csv`

---

## 6. Plot Ranges

```bash
uv run python/python/plot_lp_ranges.py test_ranges.json --show-weights
```

---

## 7. Flags Reference

See README in main repo for full table.

---

## 8. Troubleshooting

- Ensure `foundry.toml` allows writing to `./script-output`
- Use current Anvil private key

---

## License

MIT  
(c) 2025
