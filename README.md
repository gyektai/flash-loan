# flash-loan

Create a smart contract that can manage funding flash loans at a ~1% cost

Call the app with args 'loan' and then the amount of your loan, and as long as it's repayed with 1% interest in the same group of transactions, then you'll have access to the funds

Call the app with args 'fund' to increase your amount staked, after opting in, with the funding payment being the first transaction in the group

Call the app with args 'withdraw' and to decrease your amount staked

Opt in to the app in a group transaction with payment being the first transaction and start staking algos and earning interest on them

Close out your participation in the contract to receive all of your stake
