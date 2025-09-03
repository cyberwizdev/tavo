mod cli;
mod fs_router;
mod swc_build;
mod bundler;
mod ssr;
mod output;
mod utils;

use anyhow::Result;
use clap::Parser;
use cli::Args;
use output::{ErrorOutput, OutputManager};
use std::process;

#[tokio::main]
async fn main() {
    let args = Args::parse();
    
    // Set up logging
    utils::setup_logging(&args.log_level);
    
    if let Err(e) = run(args).await {
        let error_output = ErrorOutput {
            error: output::ErrorDetails {
                kind: "InternalError".to_string(),
                message: format!("{:#}", e),
            },
        };
        
        eprintln!("{}", serde_json::to_string(&error_output).unwrap());
        process::exit(1);
    }
}

async fn run(args: Args) -> Result<()> {
    // Step 1: Resolve route and extract params
    let route_info = fs_router::resolve_route(&args.route, &args.app_dir)?;
    
    // Step 2: Generate virtual entry code
    let virtual_entry = bundler::generate_virtual_entry(&route_info, &args)?;
    
    // Step 3: Transpile with SWC
    let transpiled_code = swc_build::transpile_code(&virtual_entry, &args)?;
    
    // Step 4 & 5: Generate output based on compile type
    let output_data = match args.compile_type.as_str() {
        "hydration" => {
            output::generate_hydration_output(&transpiled_code, &route_info.params)
        }
        "ssr" => {
            let html = ssr::render_to_string(&transpiled_code, &route_info.params, args.timeout_ms).await?;
            output::generate_ssr_output(&html, &transpiled_code, &route_info.params)
        }
        _ => unreachable!(),
    };
    
    // Output based on format
    let output_manager = OutputManager::new(args.output);
    output_manager.write_output(&output_data)?;
    
    Ok(())
}