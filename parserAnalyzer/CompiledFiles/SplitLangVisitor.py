# Generated from parserAnalyzer\SplitLang.g4 by ANTLR 4.9.2
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .SplitLangParser import SplitLangParser
else:
    from SplitLangParser import SplitLangParser

# This class defines a complete generic visitor for a parse tree produced by SplitLangParser.

class SplitLangVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SplitLangParser#program.
    def visitProgram(self, ctx:SplitLangParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#stmtSep.
    def visitStmtSep(self, ctx:SplitLangParser.StmtSepContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#statement.
    def visitStatement(self, ctx:SplitLangParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#groupStmt.
    def visitGroupStmt(self, ctx:SplitLangParser.GroupStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#currencyStmt.
    def visitCurrencyStmt(self, ctx:SplitLangParser.CurrencyStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#AddMembersStmt.
    def visitAddMembersStmt(self, ctx:SplitLangParser.AddMembersStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#RemoveMembersStmt.
    def visitRemoveMembersStmt(self, ctx:SplitLangParser.RemoveMembersStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#expenseStmt.
    def visitExpenseStmt(self, ctx:SplitLangParser.ExpenseStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#EqualSplit.
    def visitEqualSplit(self, ctx:SplitLangParser.EqualSplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ShorthandEqualSplit.
    def visitShorthandEqualSplit(self, ctx:SplitLangParser.ShorthandEqualSplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExactSplit.
    def visitExactSplit(self, ctx:SplitLangParser.ExactSplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#PercentSplit.
    def visitPercentSplit(self, ctx:SplitLangParser.PercentSplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#RatioSplit.
    def visitRatioSplit(self, ctx:SplitLangParser.RatioSplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#TaxMod.
    def visitTaxMod(self, ctx:SplitLangParser.TaxModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#TipMod.
    def visitTipMod(self, ctx:SplitLangParser.TipModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#DiscountMod.
    def visitDiscountMod(self, ctx:SplitLangParser.DiscountModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#dateClause.
    def visitDateClause(self, ctx:SplitLangParser.DateClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#billStmt.
    def visitBillStmt(self, ctx:SplitLangParser.BillStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillItemEntry.
    def visitBillItemEntry(self, ctx:SplitLangParser.BillItemEntryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillTaxEntry.
    def visitBillTaxEntry(self, ctx:SplitLangParser.BillTaxEntryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillTipEntry.
    def visitBillTipEntry(self, ctx:SplitLangParser.BillTipEntryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillDiscountEntry.
    def visitBillDiscountEntry(self, ctx:SplitLangParser.BillDiscountEntryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#DirectPaySettle.
    def visitDirectPaySettle(self, ctx:SplitLangParser.DirectPaySettleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#KeywordSettle.
    def visitKeywordSettle(self, ctx:SplitLangParser.KeywordSettleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#settleUpStmt.
    def visitSettleUpStmt(self, ctx:SplitLangParser.SettleUpStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ShowQuery.
    def visitShowQuery(self, ctx:SplitLangParser.ShowQueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#WhoOwesWhomQuery.
    def visitWhoOwesWhomQuery(self, ctx:SplitLangParser.WhoOwesWhomQueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#HowMuchOwesQuery.
    def visitHowMuchOwesQuery(self, ctx:SplitLangParser.HowMuchOwesQueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#PersonBalanceQuery.
    def visitPersonBalanceQuery(self, ctx:SplitLangParser.PersonBalanceQueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#queryTarget.
    def visitQueryTarget(self, ctx:SplitLangParser.QueryTargetContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#UndoCtrl.
    def visitUndoCtrl(self, ctx:SplitLangParser.UndoCtrlContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ResetCtrl.
    def visitResetCtrl(self, ctx:SplitLangParser.ResetCtrlContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ClearCtrl.
    def visitClearCtrl(self, ctx:SplitLangParser.ClearCtrlContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#HelpCtrl.
    def visitHelpCtrl(self, ctx:SplitLangParser.HelpCtrlContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#personList.
    def visitPersonList(self, ctx:SplitLangParser.PersonListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#exactAllocList.
    def visitExactAllocList(self, ctx:SplitLangParser.ExactAllocListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#exactAlloc.
    def visitExactAlloc(self, ctx:SplitLangParser.ExactAllocContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#percentAllocList.
    def visitPercentAllocList(self, ctx:SplitLangParser.PercentAllocListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#percentAlloc.
    def visitPercentAlloc(self, ctx:SplitLangParser.PercentAllocContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ratioAllocList.
    def visitRatioAllocList(self, ctx:SplitLangParser.RatioAllocListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ratioAlloc.
    def visitRatioAlloc(self, ctx:SplitLangParser.RatioAllocContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MulDivExpr.
    def visitMulDivExpr(self, ctx:SplitLangParser.MulDivExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ParenExpr.
    def visitParenExpr(self, ctx:SplitLangParser.ParenExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#AtomExpr.
    def visitAtomExpr(self, ctx:SplitLangParser.AtomExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#AddSubExpr.
    def visitAddSubExpr(self, ctx:SplitLangParser.AddSubExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#amountAtom.
    def visitAmountAtom(self, ctx:SplitLangParser.AmountAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#person.
    def visitPerson(self, ctx:SplitLangParser.PersonContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#description.
    def visitDescription(self, ctx:SplitLangParser.DescriptionContext):
        return self.visitChildren(ctx)



del SplitLangParser