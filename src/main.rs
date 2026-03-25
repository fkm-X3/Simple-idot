mod lexer;
mod config;

use lexer::{Lexer, Token};
use config::IdotConfig; // import config struct
use std::fs;

fn main() {
    // Initialize your global settings
    let settings = IdotConfig::default();
    
    println!("--- simple-idot v{} ---", settings.version);

    let input = fs::read_to_string("../showcase.idot")
        .expect("Could not read the file");

    let mut lexer = Lexer::new(&input);

    // You can now pass 'settings' into your lexer if needed
    loop {
        let token = lexer.next_token();
        if token == Token::EOF { break; }
        println!("{:?}", token);
    }
}