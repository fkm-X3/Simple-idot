mod lexer; // rust looks for lexer.rs

use lexer::{Lexer, Token};
use std::fs;

fn main() {
    // reads showcase.idot file
    let input = fs::read_to_string(".//showcase.idot")
        .expect("Could not read the file");

    // init lexer
    let mut lexer = Lexer::new(&input);

    // loop through and print tokens until EOF
    loop {
        let token = lexer.next_token();
        println!("{:?}", token);

        if token == Token::EOF {
            break;
        }
    }
}