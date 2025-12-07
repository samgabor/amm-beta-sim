// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import { Script } from "forge-std/Script.sol";
import { console } from "forge-std/console.sol";

import { SwapHelper } from "../src/SwapHelper.sol";

contract TestSwapUsingHelperScript is Script {
    // Deployed SwapHelper address from your logs
    address constant SWAP_HELPER = 0x4A679253410272dd5232B3Ff7cF5dbB88f295319;


    function run() external {
        uint256 deployerPk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPk);

        vm.startBroadcast(deployerPk);

        console.log("Deployer:", deployer);
        console.log("SwapHelper:", SWAP_HELPER);

        SwapHelper helper = SwapHelper(SWAP_HELPER);

        uint256 amountIn = 0.001 ether; // swap 1 WETH from helper's balance into USDC

        console.log("Calling swapExact0For1, amountIn (wei):", amountIn);
        helper.swapExact0For1(amountIn);
        console.log("Swap done");

        vm.stopBroadcast();
    }
}
