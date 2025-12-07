// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import { Script } from "forge-std/Script.sol";
import { console } from "forge-std/console.sol";

import { IUniswapV3Pool } from "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import { LPHelper } from "../src/LPHelper.sol";
import { MockERC20 } from "../src/tokens/MockERC20.sol";

contract DeployLPHelperScript is Script {
    // Existing deployed contracts (from your config.py)
    address constant WETH    = 0x959922bE3CAee4b8Cd9a407cc3ac1C251C2007B1;
    address constant USDC    = 0x9A9f2CCfdE556A7E9Ff0848998Aa4a0CFD8863AE;
    address constant POOL    = 0x07E34a293602ef478855306c37F9DC3b98613632;

    function run() external {
        uint256 deployerPk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPk);

        vm.startBroadcast(deployerPk);

        console.log("Deployer:", deployer);

        IUniswapV3Pool pool = IUniswapV3Pool(POOL);
        address token0 = pool.token0();
        address token1 = pool.token1();

        console.log("Pool token0:", token0);
        console.log("Pool token1:", token1);

        // Deploy LPHelper wired to the actual pool token ordering
        LPHelper helper = new LPHelper(token0, token1, POOL);
        console.log("LPHelper:", address(helper));

        // Fund helper with some WETH and USDC from deployer so it can pay the mint callback
        MockERC20 weth = MockERC20(WETH);
        MockERC20 usdc = MockERC20(USDC);

        // Seed LPHelper with modest balances
        uint256 seedAmountWeth = 10 ether;             // 10 WETH
        uint256 seedAmountUsdc = 50_000_000_000;       // 50,000 USDC (5e4 * 1e6)

        require(weth.transfer(address(helper), seedAmountWeth), "WETH seed transfer failed");
        require(usdc.transfer(address(helper), seedAmountUsdc), "USDC seed transfer failed");

        console.log("Seeded LPHelper with WETH & USDC");

        // Much smaller full-range liquidity to avoid huge token requirements at price=3500
        uint128 liquidity = 1_000_000_000;            // 1e9

        //helper.mintFullRange(liquidity);

        // Example: full-range-style position (depends on your fee tier / spacing)
        int24 tickLower = -887220;
        int24 tickUpper =  887220;

        helper.mintRange(tickLower, tickUpper, liquidity);


        console.log("Minted liquidity:", uint256(liquidity));


        vm.stopBroadcast();
    }
}
