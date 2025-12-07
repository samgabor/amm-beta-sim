// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import { IUniswapV3Pool } from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import { IUniswapV3SwapCallback } from "@uniswap/v3-core/contracts/interfaces/callback/IUniswapV3SwapCallback.sol";
import { TickMath } from "@uniswap/v3-core/contracts/libraries/TickMath.sol";

import { MockERC20 } from "./tokens/MockERC20.sol";

contract SwapHelper is IUniswapV3SwapCallback {
    // Immutable config
    address public immutable TOKEN0;
    address public immutable TOKEN1;
    address public immutable POOL;

    // Max tick move allowed per swap (slippage bound)
    // You can tune this: smaller => stricter price protection
    int24 public constant MAX_TICK_MOVE = 500; // ~0.5k ticks

    constructor(address _token0, address _token1, address _pool) {
        TOKEN0 = _token0;
        TOKEN1 = _token1;
        POOL   = _pool;
    }

    /// @notice Swap exact TOKEN0 for TOKEN1, using this contract's balances.
    /// Before calling, send TOKEN0 to this contract.
    function swapExact0For1(uint256 amountIn) external {
        require(amountIn > 0, "amountIn = 0");

        // Read current tick
        (, int24 currentTick, , , , , ) = IUniswapV3Pool(POOL).slot0();

        // Set a lower price limit: don't let price go below (tick - MAX_TICK_MOVE)
        int24 targetTick = currentTick - MAX_TICK_MOVE;
        if (targetTick < TickMath.MIN_TICK) {
            targetTick = TickMath.MIN_TICK;
        }

        uint160 sqrtPriceLimitX96 = TickMath.getSqrtRatioAtTick(targetTick);

        // casting to 'int256' is safe because 'amountIn' is a uint256 < 2^255 in our controlled test env
        // forge-lint: disable-next-line(unsafe-typecast)
        int256 signedAmountIn = int256(amountIn);

        IUniswapV3Pool(POOL).swap(
            address(this),
            true, // zeroForOne: TOKEN0 -> TOKEN1
            signedAmountIn,
            sqrtPriceLimitX96,
            bytes("")
        );
    }

    /// @notice Swap exact TOKEN1 for TOKEN0, using this contract's balances.
    /// Before calling, send TOKEN1 to this contract.
    function swapExact1For0(uint256 amountIn) external {
        require(amountIn > 0, "amountIn = 0");

        // Read current tick
        (, int24 currentTick, , , , , ) = IUniswapV3Pool(POOL).slot0();

        // Set an upper price limit: don't let price go above (tick + MAX_TICK_MOVE)
        int24 targetTick = currentTick + MAX_TICK_MOVE;
        if (targetTick > TickMath.MAX_TICK) {
            targetTick = TickMath.MAX_TICK;
        }

        uint160 sqrtPriceLimitX96 = TickMath.getSqrtRatioAtTick(targetTick);

        // casting to 'int256' is safe because 'amountIn' is a uint256 < 2^255 in our controlled test env
        // forge-lint: disable-next-line(unsafe-typecast)
        int256 signedAmountIn = int256(amountIn);

        IUniswapV3Pool(POOL).swap(
            address(this),
            false, // zeroForOne: TOKEN1 -> TOKEN0
            signedAmountIn,
            sqrtPriceLimitX96,
            bytes("")
        );
    }

    /// @inheritdoc IUniswapV3SwapCallback
    function uniswapV3SwapCallback(
        int256 amount0Delta,
        int256 amount1Delta,
        bytes calldata /* data */
    ) external override {
        require(msg.sender == POOL, "callback only from pool");

        if (amount0Delta > 0) {
            // casting to 'uint256' is safe because we only cast positive deltas
            // forge-lint: disable-next-line(unsafe-typecast)
            uint256 pay0 = uint256(amount0Delta);

            require(
                MockERC20(TOKEN0).transfer(msg.sender, pay0),
                "TOKEN0 pay failed"
            );
        }
        if (amount1Delta > 0) {
            // casting to 'uint256' is safe because we only cast positive deltas
            // forge-lint: disable-next-line(unsafe-typecast)
            uint256 pay1 = uint256(amount1Delta);

            require(
                MockERC20(TOKEN1).transfer(msg.sender, pay1),
                "TOKEN1 pay failed"
            );
        }
    }
}
