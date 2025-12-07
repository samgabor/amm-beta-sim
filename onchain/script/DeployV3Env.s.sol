// SPDX-License-Identifier: MIT
//pragma solidity ^0.8.20;
pragma solidity 0.7.6;

import { Script } from "forge-std/Script.sol";
import { console } from "forge-std/console.sol";


import { UniswapV3Factory } from "@uniswap/v3-core/contracts/UniswapV3Factory.sol";
import { IUniswapV3Pool } from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
//import { IUniswapV3Factory } from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Factory.sol";

import { MockERC20 } from "../src/tokens/MockERC20.sol";

contract DeployV3Env is Script {
    // Addresses we’ll deploy
    MockERC20 public weth;
    MockERC20 public usdc;
    UniswapV3Factory public factory;
    IUniswapV3Pool public pool;

    // constants
    uint24 public constant FEE_TIER = 3000; // 0.3%
    int24 public constant TICK_SPACING = 60; // for reference; factory sets internally

    // 1 WETH = 3,500 USDC with 18 / 6 decimals
    // sqrtPriceX96 = sqrt( (3500 * 10^6) / 10^18 ) * 2^96
    // precomputed as uint160
    function _encodePriceSqrt() internal pure returns (uint160) {
        return 4687201305027700927646044;
    }

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        console.log("Deployer:", deployer);

        // 1. Deploy tokens
        weth = new MockERC20(
            "Wrapped Ether",
            "WETH",
            18,
            1_000_000 ether, // initial supply
            deployer
        );

        usdc = new MockERC20(
            "USD Coin",
            "USDC",
            6,
            10_000_000 * 10**6, // 10M USDC
            deployer
        );

        console.log("WETH:", address(weth));
        console.log("USDC:", address(usdc));

        // 2. Deploy factory
        factory = new UniswapV3Factory();
        console.log("UniswapV3Factory:", address(factory));

        // 3. Create pool
        address poolAddress = factory.createPool(
            address(weth),
            address(usdc),
            FEE_TIER
        );
        pool = IUniswapV3Pool(poolAddress);

        console.log("WETH/USDC pool:", address(pool));

        // 4. Initialize pool price
        // For now, just initialize at sqrtPriceX96 corresponding to price=1:1
        // (we’ll handle realistic price in offchain calcs later)
        uint160 sqrtPriceX96 = _encodePriceSqrt();
        pool.initialize(sqrtPriceX96);

        vm.stopBroadcast();

        console.log("Deployment complete.");
    }
}
