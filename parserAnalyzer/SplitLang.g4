grammar SplitLang;

/*
 * SplitLang - A Domain-Specific Language (DSL) for Bill Splitting
 * Course: Principles of Programming Languages (VNU-HCM International University)
 *
 * Five-Stage PPL Architecture:
 *   Input -> Lexer (SplitLangLexer) -> Parser (SplitLangParser)
 *         -> Visitor / AST (ASTGeneration) -> Action / Engine (utilFunction + Database)
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
    : groupStmt
    | currencyStmt
    | memberStmt
    | expenseStmt
    | billStmt
    | settleStmt
    | settleUpStmt
    | queryStmt
    | controlStmt
    ;

// 1. Group & Currency Management
groupStmt
    : USE? GROUP description
    ;

currencyStmt
    : CURRENCY CURRENCY_CODE
    ;

// 2. Member Management
memberStmt
    : ADD MEMBER_KW personList          # AddMembersStmt
    | REMOVE MEMBER_KW personList       # RemoveMembersStmt
    ;

// 3. Single Expense Statement (4 split modes + modifiers + arithmetic expr)
expenseStmt
    : person PAID expr (FOR description)? splitClause? modifier* dateClause?
    ;

splitClause
    : SPLIT EQUALLY (AMONG personList | EXCLUDING personList)?   # EqualSplit
    | (AMONG personList | EXCLUDING personList)                  # ShorthandEqualSplit
    | SPLIT EXACT exactAllocList                                 # ExactSplit
    | SPLIT PERCENT percentAllocList                             # PercentSplit
    | SPLIT RATIO ratioAllocList                                 # RatioSplit
    ;

modifier
    : WITH? TAX (PERCENT_LIT | expr)        # TaxMod
    | WITH? TIP (PERCENT_LIT | expr)        # TipMod
    | WITH? DISCOUNT (PERCENT_LIT | expr)   # DiscountMod
    ;

dateClause
    : ON DATE
    ;

// 4. Itemized Bill Block Statement (block-structured DSL syntax)
billStmt
    : BILL description PAID BY person dateClause?
      LBRACE NEWLINE* billEntry (stmtSep billEntry)* stmtSep? RBRACE
    ;

billEntry
    : ITEM description expr FOR (ALL (EXCLUDING personList)? | personList)   # BillItemEntry
    | TAX (PERCENT_LIT | expr)                                               # BillTaxEntry
    | TIP (PERCENT_LIT | expr)                                               # BillTipEntry
    | DISCOUNT (PERCENT_LIT | expr)                                          # BillDiscountEntry
    ;

// 5. Settlement / Repayment Statements
settleStmt
    : person PAYS person expr (FOR description)? dateClause?                 # DirectPaySettle
    | SETTLE person TO person expr (FOR description)? dateClause?            # KeywordSettle
    ;

settleUpStmt
    : SETTLE UP
    ;

// 6. Query & Reporting Statements
queryStmt
    : (SHOW | CHECK) queryTarget                                 # ShowQuery
    | WHO OWES WHOM QUESTIONMARK?                                # WhoOwesWhomQuery
    | HOW MUCH DOES person OWES QUESTIONMARK?                    # HowMuchOwesQuery
    | WHAT IS person BALANCES QUESTIONMARK?                      # PersonBalanceQuery
    ;

queryTarget
    : MEMBER_KW
    | EXPENSES
    | BALANCES
    | SUMMARY
    | SETTLEMENTS
    | GROUPS
    ;

// 7. Control Statements
controlStmt
    : UNDO      # UndoCtrl
    | RESET     # ResetCtrl
    | CLEAR     # ClearCtrl
    | HELP      # HelpCtrl
    ;

// ============================================================================
// RECURSIVE LIST RULES (Classic CFG Right-Recursion)
// ============================================================================

personList
    : person COMMA personList
    | person
    ;

exactAllocList
    : exactAlloc COMMA exactAllocList
    | exactAlloc
    ;

exactAlloc
    : person COLON expr
    ;

percentAllocList
    : percentAlloc COMMA percentAllocList
    | percentAlloc
    ;

percentAlloc
    : person COLON PERCENT_LIT
    ;

ratioAllocList
    : ratioAlloc COMMA ratioAllocList
    | ratioAlloc
    ;

ratioAlloc
    : person COLON NUMBER
    ;

// ============================================================================
// ARITHMETIC EXPRESSION GRAMMAR (Operator Precedence & Associativity)
// ============================================================================

expr
    : expr op=(STAR | SLASH) expr       # MulDivExpr
    | expr op=(PLUS | MINUS) expr       # AddSubExpr
    | LPAREN expr RPAREN                # ParenExpr
    | amountAtom                        # AtomExpr
    ;

amountAtom
    : MONEY_K
    | MONEY_M
    | MONEY_USD
    | NUMBER
    ;

person
    : ID
    ;

description
    : STRING
    | ID+
    ;

// ============================================================================
// LEXER RULES (Case-insensitive keywords declared before general ID)
// ============================================================================

// Keywords
GROUP       : G R O U P ;
GROUPS      : G R O U P S ;
USE         : U S E ;
CURRENCY    : C U R R E N C Y ;
ADD         : A D D ;
REMOVE      : R E M O V E ;
MEMBER_KW   : M E M B E R S? ;
PAID        : P A I D | S P E N T ;
PAYS        : P A Y S | R E P A Y S ;
FOR         : F O R ;
SPLIT       : S P L I T ;
EQUALLY     : E Q U A L L Y | E Q U A L ;
EXACT       : E X A C T ;
PERCENT     : P E R C E N T | P E R C E N T A G E ;
RATIO       : R A T I O | S H A R E S | W E I G H T S? ;
AMONG       : A M O N G | B E T W E E N ;
EXCLUDING   : E X C L U D I N G | E X C E P T ;
WITH        : W I T H ;
TAX         : T A X ;
TIP         : T I P ;
DISCOUNT    : D I S C O U N T ;
ON          : O N ;
BILL        : B I L L ;
BY          : B Y ;
ITEM        : I T E M ;
SETTLE      : S E T T L E ;
UP          : U P ;
TO          : T O ;
SHOW        : S H O W ;
CHECK       : C H E C K ;
BALANCES    : B A L A N C E S? ;
EXPENSES    : E X P E N S E S? | H I S T O R Y ;
SUMMARY     : S U M M A R Y | S T A T S | S T A T I S T I C S ;
SETTLEMENTS : S E T T L E M E N T S? | T R A N S F E R S? ;
WHO         : W H O ;
OWES        : O W E S? ;
WHOM        : W H O M ;
HOW         : H O W ;
MUCH        : M U C H ;
DOES        : D O E S ;
WHAT        : W H A T ;
IS          : I S ;
UNDO        : U N D O ;
RESET       : R E S E T ;
CLEAR       : C L E A R ;
HELP        : H E L P ;
ALL         : A L L ;

CURRENCY_CODE
    : V N D
    | U S D
    | E U R
    | J P Y
    | G B P
    | S G D
    ;

// Literals (order matters: more specific tokens first)
DATE
    : [0-9][0-9] ('-' | '/') [0-9][0-9] ('-' | '/') [0-9][0-9][0-9][0-9]
    | [0-9][0-9][0-9][0-9] '-' [0-9][0-9] '-' [0-9][0-9]
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

// Identifiers (fallback after keywords)
ID          : [a-zA-Z_] [a-zA-Z0-9_'-]* ;

// Operators & Punctuation
PLUS        : '+' ;
MINUS       : '-' ;
STAR        : '*' ;
SLASH       : '/' ;
LPAREN      : '(' ;
RPAREN      : ')' ;
LBRACE      : '{' ;
RBRACE      : '}' ;
COMMA       : ',' ;
COLON       : ':' ;
SEMI        : ';' ;
QUESTIONMARK: '?' ;

// Comments, Newlines, and Whitespace
LINE_COMMENT: ('//' | '#') ~[\r\n]* -> skip ;
NEWLINE     : '\r'? '\n' ;
WS          : [ \t]+ -> skip ;

// Case-insensitive letter fragments
fragment A : [aA] ;
fragment B : [bB] ;
fragment C : [cC] ;
fragment D : [dD] ;
fragment E : [eE] ;
fragment F : [fF] ;
fragment G : [gG] ;
fragment H : [hH] ;
fragment I : [iI] ;
fragment J : [jJ] ;
fragment K : [kK] ;
fragment L : [lL] ;
fragment M : [mM] ;
fragment N : [nN] ;
fragment O : [oO] ;
fragment P : [pP] ;
fragment Q : [qQ] ;
fragment R : [rR] ;
fragment S : [sS] ;
fragment T : [tT] ;
fragment U : [uU] ;
fragment V : [vV] ;
fragment W : [wW] ;
fragment X : [xX] ;
fragment Y : [yY] ;
fragment Z : [zZ] ;
