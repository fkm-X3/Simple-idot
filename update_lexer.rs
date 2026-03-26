/// Tool to automatically update the lexer based on syntax.toml
/// 
/// Usage: cargo run --bin update_lexer
/// 
/// This reads syntax.toml and regenerates parts of src/lexer.rs

use std::fs;

fn main() {
    println!("Simple-idot Lexer Update Tool");
    println!("================================\n");

    // Read syntax.toml
    let syntax_content = fs::read_to_string("syntax.toml")
        .expect("Failed to read syntax.toml");
    
    let (keywords, builtins) = parse_syntax_toml(&syntax_content);
    
    println!(" Found {} keywords", keywords.len());
    println!(" Found {} built-in functions", builtins.len());
    
    // Generate Token enum variants
    let token_variants = generate_token_variants(&keywords, &builtins);
    
    // Generate match arms for keyword/builtin recognition
    let match_arms = generate_match_arms(&keywords, &builtins);
    
    println!("\n✨ Generated code:\n");
    println!("--- Token Enum Additions ---");
    println!("{}", token_variants);
    println!("\n--- Match Arms ---");
    println!("{}", match_arms);
}

fn parse_syntax_toml(content: &str) -> (Vec<String>, Vec<String>) {
    let mut keywords = Vec::new();
    let mut builtins = Vec::new();
    let mut current_section = "";
    let mut in_array = false;
    let mut array_content = String::new();
    
    for line in content.lines() {
        let line = line.trim();
        
        // Skip comments and empty lines
        if line.starts_with('#') || line.is_empty() {
            continue;
        }
        
        if line.starts_with('[') && line.ends_with(']') {
            current_section = &line[1..line.len()-1];
        } else if line.starts_with("items = [") || line.starts_with("functions = [") {
            if line.ends_with(']') {
                // Single line array
                if let (Some(start), Some(end)) = (line.find('['), line.rfind(']')) {
                    let items_str = &line[start+1..end];
                    let items = parse_array_items(items_str);
                    
                    if current_section == "keywords" {
                        keywords = items;
                    } else if current_section == "builtins" {
                        builtins = items;
                    }
                }
            } else {
                // Multi-line array start
                in_array = true;
                if let Some(start) = line.find('[') {
                    array_content = line[start+1..].to_string();
                }
            }
        } else if in_array {
            if line.ends_with(']') {
                // End of multi-line array
                array_content.push_str(line.trim_end_matches(']'));
                let items = parse_array_items(&array_content);
                
                if current_section == "keywords" {
                    keywords = items;
                } else if current_section == "builtins" {
                    builtins = items;
                }
                
                in_array = false;
                array_content.clear();
            } else {
                array_content.push_str(line);
            }
        }
    }
    
    (keywords, builtins)
}

fn parse_array_items(items_str: &str) -> Vec<String> {
    items_str
        .split(',')
        .map(|s| s.trim().trim_matches('"').to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

fn generate_token_variants(keywords: &[String], builtins: &[String]) -> String {
    let mut output = String::new();
    
    output.push_str("    // Keywords\n    ");
    let keyword_variants: Vec<String> = keywords.iter()
        .map(|kw| to_pascal_case(kw))
        .collect();
    output.push_str(&keyword_variants.join(", "));
    output.push_str(",\n");
    
    if !builtins.is_empty() {
        output.push_str("\n    // Built-in Functions\n    ");
        let builtin_variants: Vec<String> = builtins.iter()
            .map(|b| to_pascal_case(b))
            .collect();
        output.push_str(&builtin_variants.join(", "));
        output.push_str(",\n");
    }
    
    output
}

fn generate_match_arms(keywords: &[String], builtins: &[String]) -> String {
    let mut output = String::new();
    
    for kw in keywords {
        output.push_str(&format!("            \"{}\" => Token::{},\n", kw, to_pascal_case(kw)));
    }
    
    for builtin in builtins {
        output.push_str(&format!("            \"{}\" => Token::{},\n", builtin, to_pascal_case(builtin)));
    }
    
    output.push_str("            _ => Token::Identifier(ident),\n");
    
    output
}

fn to_pascal_case(s: &str) -> String {
    s.split('_')
        .map(|word| {
            let mut chars = word.chars();
            match chars.next() {
                None => String::new(),
                Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
            }
        })
        .collect()
}
