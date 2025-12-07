// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import { IUniswapV3Pool } from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import { IUniswapV3MintCallback } from "@uniswap/v3-core/contracts/interfaces/callback/IUniswapV3MintCallback.sol";

import { MockERC20 } from "./tokens/MockERC20.sol";

/// @notice Helper contract that:
///  - holds LP capital (token0, token1)
///  - mints Uniswap V3 liquidity across ranges
///  - relies on off-chain code for valuation and fee accounting
contract LPHelper is IUniswapV3MintCallback {
    address public immutable TOKEN0;
    address public immutable TOKEN1;
    address public immutable POOL; // Uniswap V3 pool (token0/token1, single fee tier)

    constructor(address _token0, address _token1, address _pool) {
        TOKEN0 = _token0;
        TOKEN1 = _token1;
        POOL = _pool;
    }

    // ===========================
    // Mint helpers
    // ===========================

    /// @notice Mint liquidity for a single tick range.
    /// @dev The owed token0/token1 are paid from this contract in the mint callback.
    function mintRange(
        int24 tickLower,
        int24 tickUpper,
        uint128 liquidity
    ) public returns (uint256 amount0, uint256 amount1) {
        require(liquidity > 0, "liquidity=0");

        // Uniswap v3 mint call
        (amount0, amount1) = IUniswapV3Pool(POOL).mint(
            address(this),
            tickLower,
            tickUpper,
            liquidity,
            bytes("") // no extra data; callback only needs msg.sender == POOL
        );
    }

    /// @notice Mint multiple ranges at once (beta ranges).
    /// @return total0 total amount of token0 required across all mints
    /// @return total1 total amount of token1 required across all mints
    function mintRanges(
        int24[] calldata tickLowers,
        int24[] calldata tickUppers,
        uint128[] calldata liquidities
    ) external returns (uint256 total0, uint256 total1) {
        require(
            tickLowers.length == tickUppers.length &&
                tickLowers.length == liquidities.length,
            "array length mismatch"
        );

        for (uint256 i = 0; i < tickLowers.length; i++) {
            (uint256 amt0, uint256 amt1) = mintRange(
                tickLowers[i],
                tickUppers[i],
                liquidities[i]
            );
            total0 += amt0;
            total1 += amt1;
        }
    }

    /// @dev Uniswap V3 mint callback. Pays the pool what is owed in token0/token1.
    function uniswapV3MintCallback(
        uint256 amount0Owed,
        uint256 amount1Owed,
        bytes calldata /* data */
    ) external override {
        require(msg.sender == POOL, "caller not pool");

        if (amount0Owed > 0) {
            require(
                MockERC20(TOKEN0).transfer(msg.sender, amount0Owed),
                "TOKEN0 transfer failed"
            );
        }
        if (amount1Owed > 0) {
            require(
                MockERC20(TOKEN1).transfer(msg.sender, amount1Owed),
                "TOKEN1 transfer failed"
            );
        }
    }
}
