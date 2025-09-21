use clap::Parser;
use anyhow::Result;
use std::path::PathBuf;

mod cli;
mod compiler;
mod bundler;
mod ssr;
mod hydration;
mod utils;

use cli::Args;
use compiler::Compiler;

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    
    let mut compiler = Compiler::new()?;
    
    match (args.ssr, args.hydrate, args.out.as_ref()) {
        // SSR only
        (true, false, None) => {
            let html = compiler.render_ssr(&args.entry).await?;
            println!("{}", html);
        }
        
        // Hydration only
        (false, true, None) => {
            let js = compiler.generate_hydration_script(&args.entry).await?;
            println!("{}", js);
        }
        
        // Both SSR and hydration to file
        (true, true, Some(output)) => {
            let html = compiler.render_ssr(&args.entry).await?;
            let js = compiler.generate_hydration_script(&args.entry).await?;
            let full_html = compiler.combine_html_and_script(&html, &js)?;
            std::fs::write(output, full_html)?;
            eprintln!("Generated: {}", output.display());
        }
        
        // SSR to file
        (true, false, Some(output)) => {
            let html = compiler.render_ssr(&args.entry).await?;
            std::fs::write(output, html)?;
            eprintln!("Generated: {}", output.display());
        }
        
        // Hydration to file
        (false, true, Some(output)) => {
            let js = compiler.generate_hydration_script(&args.entry).await?;
            std::fs::write(output, js)?;
            eprintln!("Generated: {}", output.display());
        }
        
        _ => {
            eprintln!("Error: Must specify either --ssr, --hydrate, or both");
            std::process::exit(1);
        }
    }
    
    Ok(())
}