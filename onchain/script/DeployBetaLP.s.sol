// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import { Script } from "forge-std/Script.sol";
import { console } from "forge-std/console.sol";

import { LPHelper } from "../src/LPHelper.sol";
import { MockERC20 } from "../src/tokens/MockERC20.sol";

// ============================================
//   CONFIGURATION: UPDATE THESE BEFORE RUNNING
// ============================================

// address constant WETH  = 0x5FbDB2315678afecb367f032d93F642f64180aa3;
// address constant USDC  = 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512;
// address constant LPHELPER_ADDR = 0x5FC8d32690cc91D4c39d9d3abcBD16989F875707;

contract DeployBetaLP is Script {

    struct Addresses {
        address weth;
        address usdc;
        address factory;
        address router;
        address pool;
        address lp_helper;
        address swap_helper;
    }

    function run() external {
        // ===========================
        // LOAD DEPLOYER
        // ===========================
        uint256 pk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(pk);
        vm.startBroadcast(pk);

        // ============================================================
        // 1. Load addresses.json
        // ============================================================

        string memory json1 = vm.readFile("script/addresses.json");

        Addresses memory addrs = Addresses({
            weth:        vm.parseJsonAddress(json1, ".weth"),
            usdc:        vm.parseJsonAddress(json1, ".usdc"),
            factory:     vm.parseJsonAddress(json1, ".factory"),
            router:      vm.parseJsonAddress(json1, ".router"),
            pool:        vm.parseJsonAddress(json1, ".pool"),
            lp_helper:   vm.parseJsonAddress(json1, ".lp_helper"),
            swap_helper: vm.parseJsonAddress(json1, ".swap_helper")
        });

        console.log("Loaded WETH:", addrs.weth);
        console.log("Loaded USDC:", addrs.usdc);
        console.log("Loaded LPHelper:", addrs.lp_helper);
        console.log("Loaded pool:", addrs.pool);

        // ============================================================
        // 2. Use dynamic addresses
        // ============================================================

        // MockERC20 weth = MockERC20(addrs.weth);
        // MockERC20 usdc = MockERC20(addrs.usdc);
        LPHelper helper = LPHelper(addrs.lp_helper);



        console.log("Deployer:", deployer);
        //console.log("LPHelper:", LPHELPER_ADDR);

        //LPHelper helper = LPHelper(LPHELPER_ADDR);

        // ===================================================
        // READ JSON INPUT FROM FILE: ON-CHAIN BETA POSITIONS
        //
        // Expected format (beta_ranges.json):
        // {
        //   "tickLowers": [...],
        //   "tickUppers": [...],
        //   "liquidities": [...]
        // }
        // ===================================================

        // Reading local JSON config is intentional here.
        // forge-lint: disable-next-line(unsafe-cheatcode)
        string memory json = vm.readFile("script/beta_ranges.json");


        // parse as int256[] then cast to int24[]
        int256[] memory tickLowers256 = vm.parseJsonIntArray(json, "$.tickLowers");
        int256[] memory tickUppers256 = vm.parseJsonIntArray(json, "$.tickUppers");

        uint256 n = tickLowers256.length;
        require(tickUppers256.length == n, "length mismatch (ticks)");

        int24[] memory tickLowers = new int24[](n);
        int24[] memory tickUppers = new int24[](n);

        for (uint256 i = 0; i < n; i++) {
            tickLowers[i] = int24(tickLowers256[i]);
            tickUppers[i] = int24(tickUppers256[i]);
        }

        uint128[] memory liquidities = abi.decode(
            vm.parseJson(json, "$.liquidities"),
            (uint128[])
        );



        console.log("Loaded", n, "ranges from beta_ranges.json");

        // ===============================
        // FUND LPHelper BEFORE MINTING
        // ===============================

        // Measure needed liquidity from Python
        // so you know the required amounts in advance.
        // For simple testing, send a large buffer:

        // uint256 fundWeth = 500_000 ether;
        // uint256 fundUsdc = 100_000_000_000 * 1e6; // 100M USDC simulated

        uint256 fundWeth = 20 ether;
        uint256 fundUsdc = 100_000e6;

        require(
            MockERC20(addrs.weth).transfer(addrs.lp_helper, fundWeth),
            "WETH transfer to LPHelper failed"
        );
        require(
            MockERC20(addrs.usdc).transfer(addrs.lp_helper, fundUsdc),
            "USDC transfer to LPHelper failed"
        );


        console.log("Funded LPHelper with:");
        console.log(" WETH:", fundWeth);
        console.log(" USDC:", fundUsdc);

        // ===============================
        // MINT ALL BETA RANGES
        // ===============================

        (uint256 tot0, uint256 tot1) = helper.mintRanges(
            tickLowers,
            tickUppers,
            liquidities
        );

        console.log("Minted Beta-position liquidity");
        console.log("Total amount0 required:", tot0);
        console.log("Total amount1 required:", tot1);

        vm.stopBroadcast();
    }
}
