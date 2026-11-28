grammar SplitLang;

/*
 * SplitLang v2.0 — A Professional Domain-Specific Language for Bill Splitting
 * Course: Principles of Programming Languages (VNU-HCM International University)
 *
 * Language Features:
 *   - Declarative workspace blocks (`workspace "..." { currency: ...; members: [...] }`)
 *   - Typed variable bindings & Symbol Table (`let vat = 10%`, `let drinkers = all - [charlie]`)
 *   - Dimensional Type System (MONEY, SCALAR, PERCENT, MEMBER_SET)
 *   - Unified expression grammar with unary minus, operator precedence (* / > + -), & set algebra
 *   - Reusable named split rules (`rule host_weighted = ratio { alice: 2, bob: 1 }`)
 *   - Concise inline expenses & structured expense/itemized bill blocks
 *   - Explicit arrow repayments (`transfer dave -> alice = 100k`) & runtime assertions (`assert balanced`)
 *   - Classic CFG right-recursion for identifier lists & allocation maps
 */

// ============================================================================
// PARSER RULES (Context-Free Grammar)
// ============================================================================

program
    : NEWLINE* (statement (stmtSep statement)*)? stmtSep? EOF
    ;

stmtSep
    : (SEMI | NEWLINE)+
    ;

statement
    : workspaceStmt
    | currencyStmt
    | memberStmt
    | letStmt
    | ruleStmt
    | expenseStmt
    | billStmt
    | transferStmt
    | assertStmt
    | queryStmt
    | controlStmt
    ;

// 1. Workspace & Currency Declarations
workspaceStmt
    : WORKSPACE STRING (LBRACE NEWLINE* wsField (stmtSep wsField)* stmtSep? RBRACE)?
    ;

wsField
    : CURRENCY COLON CURRENCY_CODE              # WsCurrencyField
    | MEMBERS COLON LBRACK idList? RBRACK       # WsMembersField
    ;

currencyStmt
    : CURRENCY CURRENCY_CODE
    ;

// 2. Member Mutations
memberStmt
    : MEMBER ADD LBRACK idList RBRACK           # MemberAddStmt
    | MEMBER REMOVE LBRACK idList RBRACK        # MemberRemoveStmt
    ;

// 3. Symbol Table Bindings & Reusable Split Rules
letStmt
    : LET ID ASSIGN expr
    ;

ruleStmt
    : RULE ID ASSIGN splitExpr
    ;

// 4. Expenses (Inline Expression Form & Structured Block Form)
expenseStmt
    : EXPENSE STRING PAID_BY ID ASSIGN expr (SPLIT splitExpr)? modifierClause* dateClause?    # InlineExpenseStmt
    | EXPENSE STRING LBRACE NEWLINE* expenseField (stmtSep expenseField)* stmtSep? RBRACE     # BlockExpenseStmt
    ;

expenseField
    : PAYER COLON ID                # ExpPayerField
    | AMOUNT COLON expr             # ExpAmountField
    | SPLIT COLON splitExpr         # ExpSplitField
    | DISCOUNT COLON expr           # ExpDiscountField
    | TAX COLON expr                # ExpTaxField
    | TIP COLON expr                # ExpTipField
    | DATE_KW COLON DATE            # ExpDateField
    ;

modifierClause
    : DISCOUNT expr                 # InlineDiscountMod
    | TAX expr                      # InlineTaxMod
    | TIP expr                      # InlineTipMod
    ;

dateClause
    : ON DATE
    ;

splitExpr
    : EQUAL LPAREN expr RPAREN                                  # EqualSplitExpr
    | EQUAL                                                     # EqualAllSplitExpr
    | EXACT LBRACE NEWLINE* allocList? NEWLINE* RBRACE          # ExactSplitExpr
    | PERCENT LBRACE NEWLINE* allocList? NEWLINE* RBRACE        # PercentSplitExpr
    | RATIO LBRACE NEWLINE* allocList? NEWLINE* RBRACE          # RatioSplitExpr
    | ID                                                        # RuleRefSplitExpr
    ;

// 5. Block-Structured Itemized Receipt
billStmt
    : BILL STRING LBRACE NEWLINE* billField (stmtSep billField)* stmtSep? RBRACE
    ;

billField
    : PAYER COLON ID                        # BillPayerField
    | DATE_KW COLON DATE                    # BillDateField
    | ITEM STRING ASSIGN expr FOR expr      # BillItemField
    | DISCOUNT COLON expr                   # BillDiscountField
    | TAX COLON expr                        # BillTaxField
    | TIP COLON expr                        # BillTipField
    ;

// 6. Repayment Transfers & Invariant Assertions
transferStmt
    : TRANSFER ID ARROW ID ASSIGN expr (NOTE STRING)? dateClause?
    ;

assertStmt
    : ASSERT BALANCED
    ;

// 7. Queries & Settlement
queryStmt
    : QUERY SUMMARY                         # QuerySummary
    | QUERY BALANCES                        # QueryBalances
    | QUERY BALANCE LPAREN ID RPAREN        # QueryPersonBalance
    | QUERY EXPENSES                        # QueryExpenses
    | QUERY MEMBERS                         # QueryMembers
    | QUERY GROUPS                          # QueryGroups
    | QUERY ENV                             # QueryEnv
    | SETTLE                                # SettleQuery
    ;

// 8. Control Commands
controlStmt
    : UNDO                                  # UndoCtrl
    | RESET                                 # ResetCtrl
    | CLEAR                                 # ClearCtrl
    | HELP                                  # HelpCtrl
    ;

// ============================================================================
// RECURSIVE LIST RULES (Classic CFG Right-Recursion)
// ============================================================================

idList
    : ID COMMA NEWLINE* idList
    | ID
    ;

allocList
    : allocEntry (COMMA | NEWLINE)+ allocList
    | allocEntry COMMA?
    ;

allocEntry
    : ID COLON expr
    ;

// ============================================================================
// UNIFIED TYPED EXPRESSION GRAMMAR (Arithmetic + Set Algebra + Variables)
// Precedence: Unary (-) > Mul/Div (* /) > Add/Sub (+ -)
// ============================================================================

expr
    : MINUS expr                            # UnaryNegExpr
    | expr op=(STAR | SLASH) expr           # MulDivExpr
    | expr op=(PLUS | MINUS) expr           # AddSubExpr
    | LPAREN expr RPAREN                    # ParenExpr
    | LBRACK NEWLINE* idList? NEWLINE* RBRACK  # SetLitExpr
    | ALL                                   # AllMembersExpr
    | PERCENT_LIT                           # PercentLitExpr
    | MONEY_K                               # MoneyKLitExpr
    | MONEY_M                               # MoneyMLitExpr
    | MONEY_USD                             # MoneyUsdLitExpr
    | NUMBER                                # NumberLitExpr
    | ID                                    # VarRefExpr
    ;

// ============================================================================
// LEXER RULES (Strict lowercase keywords declared before general ID)
// ============================================================================

// Declarations & Blocks
WORKSPACE   : 'workspace' ;
CURRENCY    : 'currency' ;
MEMBERS     : 'members' ;
MEMBER      : 'member' ;
ADD         : 'add' ;
REMOVE      : 'remove' ;
LET         : 'let' ;
RULE        : 'rule' ;
EXPENSE     : 'expense' ;
BILL        : 'bill' ;
ITEM        : 'item' ;
PAYER       : 'payer' ;
PAID_BY     : 'paid_by' ;
AMOUNT      : 'amount' ;
SPLIT       : 'split' ;
EQUAL       : 'equal' ;
EXACT       : 'exact' ;
PERCENT     : 'percent' ;
RATIO       : 'ratio' ;
DISCOUNT    : 'discount' ;
TAX         : 'tax' ;
TIP         : 'tip' ;
DATE_KW     : 'date' ;
FOR         : 'for' ;
ALL         : 'all' ;
ON          : 'on' ;
TRANSFER    : 'transfer' ;
NOTE        : 'note' ;
ASSERT      : 'assert' ;
BALANCED    : 'balanced' ;
QUERY       : 'query' ;
SUMMARY     : 'summary' ;
BALANCES    : 'balances' ;
BALANCE     : 'balance' ;
EXPENSES    : 'expenses' ;
GROUPS      : 'groups' ;
ENV         : 'env' ;
SETTLE      : 'settle' ;
UNDO        : 'undo' ;
RESET       : 'reset' ;
CLEAR       : 'clear' ;
HELP        : 'help' ;

CURRENCY_CODE
    : 'VND' | 'USD' | 'EUR' | 'JPY' | 'GBP' | 'SGD'
    ;

// Literals (specific tokens before general NUMBER / ID)
DATE
    : [0-9][0-9][0-9][0-9] '-' [0-9][0-9] '-' [0-9][0-9]
    | [0-9][0-9] '-' [0-9][0-9] '-' [0-9][0-9][0-9][0-9]
    ;

PERCENT_LIT : [0-9]+ ('.' [0-9]+)? '%' ;
MONEY_K     : [0-9]+ ('.' [0-9]+)? [kK] ;
MONEY_M     : [0-9]+ ('.' [0-9]+)? [mM] ;
MONEY_USD   : '$' [0-9]+ ('.' [0-9]+)? ;
NUMBER      : [0-9]+ ('.' [0-9]+)? ;

STRING
    : '"' ( '\\' . | ~["\\\r\n] )* '"'
    | '\'' ( '\\' . | ~['\\\r\n] )* '\''
    ;

ID          : [a-zA-Z_] [a-zA-Z0-9_-]* ;

// Operators & Punctuation (ARROW before MINUS)
ARROW       : '->' ;
ASSIGN      : '=' ;
PLUS        : '+' ;
MINUS       : '-' ;
STAR        : '*' ;
SLASH       : '/' ;
LPAREN      : '(' ;
RPAREN      : ')' ;
LBRACE      : '{' ;
RBRACE      : '}' ;
LBRACK      : '[' ;
RBRACK      : ']' ;
COMMA       : ',' ;
COLON       : ':' ;
SEMI        : ';' ;

// Comments, Newlines & Whitespace
BLOCK_COMMENT : '/*' .*? '*/' -> skip ;
LINE_COMMENT  : ('//' | '#') ~[\r\n]* -> skip ;
NEWLINE       : '\r'? '\n' ;
WS            : [ \t]+ -> skip ;
