from pyteal import *
import os

def approval_program():

    contract_addr = Global.current_application_address()
    creator = Global.creator_address()
    arg1 = Txn.application_args[0] # string used for noop determining
    arg2 = Btoi(Txn.application_args[0]) # btoi since should always be used as an int value
    staked = App.localGet(Int(0), Bytes("staked"))
    total_staked = App.globalGet(Bytes("total"))
    min_fee = Global.min_txn_fee()

    i = ScratchVar(TealType.uint64) # index used in for loops
    num_calls = ScratchVar(TealType.uint64) # number of app calls to this addr found in the gtxns

    # to make sure that the payment comes to this contract
    check_payment = And(
        Gtxn[0].type_enum() == TxnType.Payment,
        Gtxn[0].receiver() == contract_addr,
    )

    # handles creation, initializes contract with 0 staked
    handle_create = Seq(
        App.globalPut(Bytes("total"), Int(0)),
        Approve()
    )

    # makes sure the contract is paid to account for the starting stake, 
    # and sets the local and global vars
    handle_optin = Seq(
        Assert(check_payment),
        App.localPut(Int(0), Bytes("staked"), Gtxn[0].amount()),
        App.globalPut(Bytes("total"), total_staked + Gtxn[0].amount()),
        Approve()
    )

    # sends back all of the staked amount
    handle_closeout = Seq(
        InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: Txn.sender(),
                TxnField.amount: staked - min_fee,
            }),
        InnerTxnBuilder.Submit(),
        Approve()
    )

    # supplies the funds of the loan to the sender of the app call
    send_funds = Seq(
        InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: Txn.sender(),
                TxnField.amount: arg2,
            }),
        InnerTxnBuilder.Submit(),
        Approve()
    )


    # checks if the txn is repaying the loan
    def checkRepay(n):
        return And(
            Gtxn[n].receiver() == contract_addr, 
            Gtxn[n].amount() >= arg2 * Int(101) / Int(100), 
            Gtxn[n].type_enum() == TxnType.Payment
        )

    # checks for more than one borrowing app calls
    def checkDup(n):
        return Seq(
            If(And(Gtxn[n].type_enum() == TxnType.ApplicationCall, Gtxn[n].application_id() == Btoi(contract_addr)),
                If(num_calls.load() == Int(1), 
                    Reject(), 
                    num_calls.store(Int(1))
                )
            ),
            Int(1)
        )

    # when someone wants a flash loan
    handle_loan = Seq(
        num_calls.store(Int(0)),
        # make sure there aren't 2 loan calls
        For(i.store(Int(0)), i.load() < Global.group_size(), i.store(i.load() + Int(1))).Do(
            If(checkDup(i.load()),
                i.store(i.load() + Int(1)),
                Reject())),
        # make sure loan is repayed
        For(i.store(Int(0)), i.load() < Global.group_size(), i.store(i.load() + Int(1))).Do(
            If(checkRepay(i.load()),
                send_funds, # will Approve() if evaluated properly
                i.store(i.load() + Int(1)))),
        Reject()
    )

    # handles when someone wants to increase their amount staked
    handle_fund = Seq(
        Assert(check_payment),
        App.localPut(Int(0), Bytes("staked"), staked + Gtxn[0].amount()),
        App.globalPut(Bytes("total"), total_staked + Gtxn[0].amount()),
        Approve()
    )

    # handles when someone wants to decrease their amount staked
    handle_withdrawal = Seq(
        Assert(arg2 <= staked),
        InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: Txn.sender(),
                TxnField.amount: arg2,
            }),
        InnerTxnBuilder.Submit(),
        App.localPut(Int(0), Bytes("staked"), staked - arg2 - min_fee),
        Approve()
    )

    # handles the redemption of borrowing fees
    handle_redeem = Seq(
        InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: creator,
                TxnField.amount: Balance(contract_addr) - total_staked - MinBalance(contract_addr) - min_fee,
            }),
        InnerTxnBuilder.Submit(),
        Approve()
    )

    handle_noop = Cond(
        [arg1 == Bytes("fund"), handle_fund],
        [arg1 == Bytes("withdraw"), handle_withdrawal],
        [arg1 == Bytes("loan"), handle_loan],
        [arg1 == Bytes("redeem"), handle_redeem]
    )

    program = Cond(
        [Txn.application_id() == Int(0), handle_create],
        [Txn.on_completion() == OnComplete.OptIn, handle_optin],
        [Txn.on_completion() == OnComplete.CloseOut, handle_closeout],
        [Txn.on_completion() == OnComplete.UpdateApplication, Reject()],
        [Txn.on_completion() == OnComplete.DeleteApplication, Reject()],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop]
    )

    return compileTeal(program, mode=Mode.Application, version=5)

# shouldn't be necessary since there's no opting in, but alway approve it
def clear_state_program():
    program = Return(Int(1))
    return compileTeal(program, mode=Mode.Application, version=5)

if __name__ == "__main__":
    path = os.path.dirname(os.path.abspath(__file__))

    with open(os.path.join(path,"flashLoanApproval.teal"), "w") as f:
        f.write(approval_program())
    
    with open(os.path.join(path,"flashLoanClear.teal"), "w") as f:
        f.write(clear_state_program())
