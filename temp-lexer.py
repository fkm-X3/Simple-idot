import re

# Token definitions
TOKEN_TYPES = [
    ('HEADER_COMMENT', r'///.*?///'),           # 
    ('DOC_COMMENT',    r'~.*?~'),               # 
    ('COMMENT',        r'//.*|/\*.*?\*/'),      # 
    ('KEYWORD',        r'\blet\b|\bconst\b|\bfn\b|\brepeat\b|\bprint\b'), # 
    ('NUMBER',         r'\d+(\.\d+)?'),         # 
    ('STRING',         r'"[^"]*"'),             # 
    ('IDENTIFIER',     r'[a-zA-Z_][a-zA-Z0-9_]*'), # 
    ('OPERATOR',       r'[=+*/-]'),             # 
    ('LBRACE',         r'\{'),                  # 
    ('RBRACE',         r'\}'),                  # 
    ('LPAREN',         r'\('),                  # 
    ('RPAREN',         r'\)'),                  # 
    ('WHITESPACE',     r'\s+'),                 # Skip whitespace
]

def lex(code):
    tokens = []
    pos = 0
    while pos < len(code):
        match = None
        for token_type, pattern in TOKEN_TYPES:
            regex = re.compile(pattern, re.DOTALL)
            match = regex.match(code, pos)
            if match:
                text = match.group(0)
                if token_type != 'WHITESPACE':  # Skip whitespace tokens
                    tokens.append((token_type, text))
                pos = match.end(0)
                break
        if not match:
            raise SyntaxError(f"Unexpected character: {code[pos]}")
    return tokens

test_code = """
let x = 10
const y = 15

print(x)
print(y)
"""

for token in lex(test_code):
    print(token)