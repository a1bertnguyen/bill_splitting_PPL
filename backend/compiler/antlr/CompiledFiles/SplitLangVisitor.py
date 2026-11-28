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


    # Visit a parse tree produced by SplitLangParser#workspaceStmt.
    def visitWorkspaceStmt(self, ctx:SplitLangParser.WorkspaceStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#WsCurrencyField.
    def visitWsCurrencyField(self, ctx:SplitLangParser.WsCurrencyFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#WsMembersField.
    def visitWsMembersField(self, ctx:SplitLangParser.WsMembersFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#currencyStmt.
    def visitCurrencyStmt(self, ctx:SplitLangParser.CurrencyStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MemberAddStmt.
    def visitMemberAddStmt(self, ctx:SplitLangParser.MemberAddStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MemberRemoveStmt.
    def visitMemberRemoveStmt(self, ctx:SplitLangParser.MemberRemoveStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#letStmt.
    def visitLetStmt(self, ctx:SplitLangParser.LetStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ruleStmt.
    def visitRuleStmt(self, ctx:SplitLangParser.RuleStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#InlineExpenseStmt.
    def visitInlineExpenseStmt(self, ctx:SplitLangParser.InlineExpenseStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BlockExpenseStmt.
    def visitBlockExpenseStmt(self, ctx:SplitLangParser.BlockExpenseStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpPayerField.
    def visitExpPayerField(self, ctx:SplitLangParser.ExpPayerFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpAmountField.
    def visitExpAmountField(self, ctx:SplitLangParser.ExpAmountFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpSplitField.
    def visitExpSplitField(self, ctx:SplitLangParser.ExpSplitFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpDiscountField.
    def visitExpDiscountField(self, ctx:SplitLangParser.ExpDiscountFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpTaxField.
    def visitExpTaxField(self, ctx:SplitLangParser.ExpTaxFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpTipField.
    def visitExpTipField(self, ctx:SplitLangParser.ExpTipFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExpDateField.
    def visitExpDateField(self, ctx:SplitLangParser.ExpDateFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#InlineDiscountMod.
    def visitInlineDiscountMod(self, ctx:SplitLangParser.InlineDiscountModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#InlineTaxMod.
    def visitInlineTaxMod(self, ctx:SplitLangParser.InlineTaxModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#InlineTipMod.
    def visitInlineTipMod(self, ctx:SplitLangParser.InlineTipModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#dateClause.
    def visitDateClause(self, ctx:SplitLangParser.DateClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#EqualSplitExpr.
    def visitEqualSplitExpr(self, ctx:SplitLangParser.EqualSplitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#EqualAllSplitExpr.
    def visitEqualAllSplitExpr(self, ctx:SplitLangParser.EqualAllSplitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ExactSplitExpr.
    def visitExactSplitExpr(self, ctx:SplitLangParser.ExactSplitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#PercentSplitExpr.
    def visitPercentSplitExpr(self, ctx:SplitLangParser.PercentSplitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#RatioSplitExpr.
    def visitRatioSplitExpr(self, ctx:SplitLangParser.RatioSplitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#RuleRefSplitExpr.
    def visitRuleRefSplitExpr(self, ctx:SplitLangParser.RuleRefSplitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#billStmt.
    def visitBillStmt(self, ctx:SplitLangParser.BillStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillPayerField.
    def visitBillPayerField(self, ctx:SplitLangParser.BillPayerFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillDateField.
    def visitBillDateField(self, ctx:SplitLangParser.BillDateFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillItemField.
    def visitBillItemField(self, ctx:SplitLangParser.BillItemFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillDiscountField.
    def visitBillDiscountField(self, ctx:SplitLangParser.BillDiscountFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillTaxField.
    def visitBillTaxField(self, ctx:SplitLangParser.BillTaxFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#BillTipField.
    def visitBillTipField(self, ctx:SplitLangParser.BillTipFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#transferStmt.
    def visitTransferStmt(self, ctx:SplitLangParser.TransferStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#assertStmt.
    def visitAssertStmt(self, ctx:SplitLangParser.AssertStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QuerySummary.
    def visitQuerySummary(self, ctx:SplitLangParser.QuerySummaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QueryBalances.
    def visitQueryBalances(self, ctx:SplitLangParser.QueryBalancesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QueryPersonBalance.
    def visitQueryPersonBalance(self, ctx:SplitLangParser.QueryPersonBalanceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QueryExpenses.
    def visitQueryExpenses(self, ctx:SplitLangParser.QueryExpensesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QueryMembers.
    def visitQueryMembers(self, ctx:SplitLangParser.QueryMembersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QueryGroups.
    def visitQueryGroups(self, ctx:SplitLangParser.QueryGroupsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#QueryEnv.
    def visitQueryEnv(self, ctx:SplitLangParser.QueryEnvContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#SettleQuery.
    def visitSettleQuery(self, ctx:SplitLangParser.SettleQueryContext):
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


    # Visit a parse tree produced by SplitLangParser#idList.
    def visitIdList(self, ctx:SplitLangParser.IdListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#allocList.
    def visitAllocList(self, ctx:SplitLangParser.AllocListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#allocEntry.
    def visitAllocEntry(self, ctx:SplitLangParser.AllocEntryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MoneyUsdLitExpr.
    def visitMoneyUsdLitExpr(self, ctx:SplitLangParser.MoneyUsdLitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MulDivExpr.
    def visitMulDivExpr(self, ctx:SplitLangParser.MulDivExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MoneyMLitExpr.
    def visitMoneyMLitExpr(self, ctx:SplitLangParser.MoneyMLitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#PercentLitExpr.
    def visitPercentLitExpr(self, ctx:SplitLangParser.PercentLitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#VarRefExpr.
    def visitVarRefExpr(self, ctx:SplitLangParser.VarRefExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#SetLitExpr.
    def visitSetLitExpr(self, ctx:SplitLangParser.SetLitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#MoneyKLitExpr.
    def visitMoneyKLitExpr(self, ctx:SplitLangParser.MoneyKLitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#NumberLitExpr.
    def visitNumberLitExpr(self, ctx:SplitLangParser.NumberLitExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#AllMembersExpr.
    def visitAllMembersExpr(self, ctx:SplitLangParser.AllMembersExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#ParenExpr.
    def visitParenExpr(self, ctx:SplitLangParser.ParenExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#AddSubExpr.
    def visitAddSubExpr(self, ctx:SplitLangParser.AddSubExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SplitLangParser#UnaryNegExpr.
    def visitUnaryNegExpr(self, ctx:SplitLangParser.UnaryNegExprContext):
        return self.visitChildren(ctx)



del SplitLangParser