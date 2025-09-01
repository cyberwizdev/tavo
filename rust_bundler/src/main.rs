use clap::{Arg, Command};
use serde_json::json;
use std::path::PathBuf;

mod compiler;
mod error;
mod layout;
mod renderer;

use crate::compiler::TSXCompiler;
use crate::error::SSRError;
use crate::layout::LayoutResolver;
use crate::renderer::SSRRenderer;

#[tokio::main]
async fn main() -> Result<(), SSRError> {
    let matches = Command::new("ssr-bundler")
        .version("1.0")
        .about("High-performance TSX SSR bundler")
        .arg(
            Arg::new("route")
                .long("route")
                .short('r')
                .value_name("ROUTE")
                .help("Route to render (e.g., /dashboard)")
                .required(true),
        )
        .arg(
            Arg::new("app-dir")
                .long("app-dir")
                .short('a')
                .value_name("DIR")
                .help("App directory path")
                .required(true),
        )
        .arg(
            Arg::new("compile-type")
                .long("compile-type")
                .short('c')
                .value_name("TYPE")
                .help("Compile type: ssr, hydration, or static")
                .default_value("ssr"),
        )
        .arg(
            Arg::new("output")
                .long("output")
                .short('o')
                .value_name("FORMAT")
                .help("Output format: json or text")
                .default_value("json"),
        )
        .get_matches();

    let route = matches.get_one::<String>("route").unwrap();
    let app_dir = PathBuf::from(matches.get_one::<String>("app-dir").unwrap());
    let compile_type = matches.get_one::<String>("compile-type").unwrap();
    let output_format = matches.get_one::<String>("output").unwrap();

    // Initialize components
    let compiler = TSXCompiler::new()?;
    let layout_resolver = LayoutResolver::new(app_dir.clone());
    let renderer = SSRRenderer::new();

    // Resolve layouts for the route
    let layouts = layout_resolver.resolve_layouts(route)?;
    
    // Compile and render
    let result = match compile_type.as_str() {
        "ssr" => {
            let compiled = compiler.compile_route_with_layouts(route, &layouts).await?;
            let html = renderer.render_to_html(&compiled).await?;
            json!({
                "html": html,
                "js": null,
                "type": "ssr"
            })
        }
        "hydration" => {
            let compiled = compiler.compile_route_with_layouts(route, &layouts).await?;
            let html = renderer.render_to_html(&compiled).await?;
            let js = compiler.compile_for_hydration(&compiled).await?;
            json!({
                "html": html,
                "js": js,
                "type": "hydration"
            })
        }
        "static" => {
            let compiled = compiler.compile_route_with_layouts(route, &layouts).await?;
            let html = renderer.render_to_static_html(&compiled).await?;
            json!({
                "html": html,
                "js": null,
                "type": "static"
            })
        }
        _ => return Err(SSRError::InvalidCompileType(compile_type.to_string())),
    };

    // Output result
    match output_format.as_str() {
        "json" => println!("{}", serde_json::to_string_pretty(&result)?),
        "text" => {
            if let Some(html) = result.get("html") {
                println!("{}", html.as_str().unwrap_or(""));
            }
        }
        _ => return Err(SSRError::InvalidOutputFormat(output_format.to_string())),
    }

    Ok(())
}
