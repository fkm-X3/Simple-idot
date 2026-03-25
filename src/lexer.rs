#[derive(Debug, PartialEq, Clone)]
pub enum Token {
    // Keywords
    Let, Const, Fn, Repeat, When, Otherwise, Bring, As, From,
    
    // Literals
    Identifier(String),
    Number(f64),
    StringLiteral(String),
    
    // Operators & Symbols
    Assign,       // =
    Plus,         // +
    Minus,        // -
    Star,         // *
    Slash,        // /
    OpenParen,    // (
    CloseParen,   // )
    OpenBrace,    // {
    CloseBrace,   // }
    Comma,        // ,
    Tilde,        // ~ (Used for doc comments/interpolation)
    
    // Special
    EOF,
}

pub struct Lexer {
    input: Vec<char>,
    pos: usize,
}

impl Lexer {
    pub fn new(input: &str) -> Self {
        Self {
            input: input.chars().collect(),
            pos: 0,
        }
    }

    // Helper to look at the current character
    fn current_char(&self) -> Option<char> {
        self.input.get(self.pos).copied()
    }

    // Advance to the next character
    fn advance(&mut self) -> Option<char> {
        let res = self.current_char();
        self.pos += 1;
        res
    }
}

impl Lexer {
    pub fn next_token(&mut self) -> Token {
        self.skip_whitespace_and_comments();

        let ch = match self.advance() {
            Some(c) => c,
            None => return Token::EOF,
        };

        match ch {
            '=' => Token::Assign,
            '+' => Token::Plus,
            '-' => Token::Minus,
            '*' => Token::Star,
            '/' => Token::Slash,
            '(' => Token::OpenParen,
            ')' => Token::CloseParen,
            '{' => Token::OpenBrace,
            '}' => Token::CloseBrace,
            ',' => Token::Comma,
            '~' => Token::Tilde,
            '"' => self.read_string(),
            '0'..='9' => self.read_number(ch),
            'a'..='z' | 'A'..='Z' | '_' => self.read_identifier(ch),
            _ => panic!("Unexpected character: {}", ch),
        }
    }

    fn read_identifier(&mut self, first_char: char) -> Token {
        let mut ident = first_char.to_string();
        while let Some(c) = self.current_char() {
            if c.is_alphanumeric() || c == '_' {
                ident.push(self.advance().unwrap());
            } else { break; }
        }

        match ident.as_str() {
            "let" => Token::Let,
            "const" => Token::Const,
            "fn" => Token::Fn,
            "repeat" => Token::Repeat,
            "when" => Token::When,
            "otherwise" => Token::Otherwise,
            "bring" => Token::Bring,
            "as" => Token::As,
            "from" => Token::From,
            _ => Token::Identifier(ident),
        }
    }

    fn read_number(&mut self, first_char: char) -> Token {
        let mut num_str = first_char.to_string();
        while let Some(c) = self.current_char() {
            if c.is_ascii_digit() || c == '.' {
                num_str.push(self.advance().unwrap());
            } else { break; }
        }
        Token::Number(num_str.parse().unwrap())
    }

    fn read_string(&mut self) -> Token {
        let mut s = String::new();
        while let Some(c) = self.advance() {
            if c == '"' { break; }
            s.push(c);
        }
        Token::StringLiteral(s)
    }

    fn skip_whitespace_and_comments(&mut self) {
        while let Some(c) = self.current_char() {
            if c.is_whitespace() {
                self.advance();
            } else if c == '/' && self.input.get(self.pos + 1) == Some(&'/') {
                // Skip single line comment
                while self.current_char() != Some('\n') && self.current_char().is_some() {
                    self.advance();
                }
            } else {
                break;
            }
        }
    }
}