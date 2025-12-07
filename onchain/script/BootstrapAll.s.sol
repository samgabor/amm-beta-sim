// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import { Script } from "forge-std/Script.sol";
import { console } from "forge-std/console.sol";

import { UniswapV3Factory } from "@uniswap/v3-core/contracts/UniswapV3Factory.sol";
import { IUniswapV3Pool } from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";

import { MockERC20 } from "../src/tokens/MockERC20.sol";
import { LPHelper } from "../src/LPHelper.sol";
import { SwapHelper } from "../src/SwapHelper.sol";

contract BootstrapAll is Script {
    // fee tier we use (0.3%)
    uint24 internal constant POOL_FEE = 3000;

    function run() external {
        uint256 pk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(pk);

        vm.startBroadcast(pk);

        console.log("Deployer:", deployer);

        // ===============================
        // 1) Deploy tokens
        // ===============================
        // MockERC20 weth = new MockERC20("Wrapped Ether", "WETH", 18);
        // MockERC20 usdc = new MockERC20("USD Coin", "USDC", 6);

        MockERC20 weth = new MockERC20(
            "Wrapped Ether",
            "WETH",
            18,
            1_000_000 ether, // initial supply
            deployer
        );

        MockERC20 usdc = new MockERC20(
            "USD Coin",
            "USDC",
            6,
            //100_000_000_000_000_000 * 10**6, // 100M USDC
            10_000_000 * 10**6, // initial supply 10M
            deployer
        );

        console.log("WETH:", address(weth));
        console.log("USDC:", address(usdc));

        // ===============================
        // 2) Deploy Uniswap V3 factory
        // ===============================
        UniswapV3Factory factory = new UniswapV3Factory();
        console.log("UniswapV3Factory:", address(factory));

        // ===============================
        // 3) Create WETH/USDC pool (fee 3000)
        // token0 must be the lower address
        // ===============================
        address token0 = address(weth) < address(usdc) ? address(weth) : address(usdc);
        address token1 = address(weth) < address(usdc) ? address(usdc) : address(weth);

        address poolAddr = factory.createPool(token0, token1, POOL_FEE);
        IUniswapV3Pool pool = IUniswapV3Pool(poolAddr);

        console.log("WETH/USDC pool:", poolAddr);

        // ===============================
        // 4) Initialize pool price at 1 ETH = 3200 USDC
        //
        // With 18-decimal WETH and 6-decimal USDC:
        //   price = (3200 * 10^6) / 10^18
        //        = 3200 / 10^12
        //
        // Uniswap v3 uses:
        //   sqrtPriceX96 = sqrt(price) * 2^96
        //
        // We compute:
        //   sqrtPriceX96 = sqrt(priceNum * 2^192 / priceDen)
        // ===============================
        //uint256 priceNum = 3200 * (10**6);  // 3200 USDC with 6 decimals
        //uint256 priceDen = 10**18;          // 1 WETH with 18 decimals

        //uint160 sqrtPriceX96 = _encodePriceSqrt(priceNum, priceDen);
        // eliminating var declarations due to limited stack space
        uint160 sqrtPriceX96 = _encodePriceSqrt(3200 * (10**6), 10**18);
        pool.initialize(sqrtPriceX96);

        console.log("Initialized pool sqrtPriceX96:", uint256(sqrtPriceX96));

        // ===============================
        // 5) Deploy helpers
        // ===============================
        LPHelper lpHelper = new LPHelper(token0, token1, poolAddr);
        SwapHelper swapHelper = new SwapHelper(token0, token1, poolAddr);

        console.log("LPHelper:", address(lpHelper));
        console.log("SwapHelper:", address(swapHelper));

        //uint256 fundWeth = 5 ether;
        //uint256 fundUsdc = 5_000_000e6; // 5M USDC simulated

        require(
            MockERC20(address(weth)).transfer(address(swapHelper), 250 ether),
            "WETH transfer to LPHelper failed"
        );
        require(
            MockERC20(address(usdc)).transfer(address(swapHelper), 100_000e6),
            "USDC transfer to LPHelper failed"
        );



        vm.stopBroadcast();

        // ===============================
        // 6) Write addresses to script/addresses.json
        // ===============================

        string memory obj = "addresses";
        string memory json = vm.serializeAddress(obj, "weth", address(weth));
        json = vm.serializeAddress(obj, "usdc", address(usdc));
        json = vm.serializeAddress(obj, "factory", address(factory));
        // no router for now; we don't need it – use zero address
        json = vm.serializeAddress(obj, "router", address(0));
        json = vm.serializeAddress(obj, "pool", poolAddr);
        json = vm.serializeAddress(obj, "lp_helper", address(lpHelper));
        json = vm.serializeAddress(obj, "swap_helper", address(swapHelper));

        // forge-lint: disable-next-line(unsafe-cheatcode)
        vm.writeJson(json, "script/addresses.json");

        console.log("Wrote addresses to script/addresses.json");
    }

    // ===============================
    // Helper: integer sqrt (Babylonian)
    // ===============================
    function _sqrt(uint256 y) internal pure returns (uint256 z) {
        if (y > 3) {
            z = y;
            uint256 x = y / 2 + 1;
            while (x < z) {
                z = x;
                x = (y / x + x) / 2;
            }
        } else if (y != 0) {
            z = 1;
        }
    }

    // ===============================
    // Encode price into sqrtPriceX96
    //
    // price = priceNum / priceDen
    // sqrtPriceX96 = sqrt(price) * 2^96
    //              = sqrt(priceNum * 2^192 / priceDen)
    // ===============================
    function _encodePriceSqrt(uint256 priceNum, uint256 priceDen) internal pure returns (uint160) {
        uint256 numerator = priceNum * (2**192);
        uint256 ratio = numerator / priceDen;
        uint256 sqrtRatio = _sqrt(ratio);
        require(sqrtRatio <= type(uint160).max, "sqrtRatio too large");
        // forge-lint: disable-next-line(unsafe-typecast)
        return uint160(sqrtRatio);
    }
}
