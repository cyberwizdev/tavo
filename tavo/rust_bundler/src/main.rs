use clap::{Arg, Command};
use serde_json::{json, Value};
use std::path::PathBuf;
use std::time::Instant;

mod compiler;
mod error;
mod layout;
mod renderer;

use crate::compiler::TSXCompiler;
use crate::error::SSRError;
use crate::layout::LayoutResolver;
use crate::renderer::{SSRRenderer, SimpleSSRRenderer};

#[derive(Debug)]
struct Config {
    route: String,
    app_dir: PathBuf,
    compile_type: CompileType,
    output_format: OutputFormat,
    verbose: bool,
    minify: bool,
    source_maps: bool,
}

#[derive(Debug, Clone)]
enum CompileType {
    Ssr,
    Hydration,
    Static,
    Debug,
}

#[derive(Debug)]
enum OutputFormat {
    Json,
    Text,
    Html,
}

impl std::str::FromStr for CompileType {
    type Err = SSRError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "ssr" => Ok(CompileType::Ssr),
            "hydration" => Ok(CompileType::Hydration),
            "static" => Ok(CompileType::Static),
            "debug" => Ok(CompileType::Debug),
            _ => Err(SSRError::InvalidCompileType(s.to_string())),
        }
    }
}

impl std::str::FromStr for OutputFormat {
    type Err = SSRError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "json" => Ok(OutputFormat::Json),
            "text" => Ok(OutputFormat::Text),
            "html" => Ok(OutputFormat::Html),
            _ => Err(SSRError::InvalidOutputFormat(s.to_string())),
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let start_time = Instant::now();
    
    match run().await {
        Ok(()) => {
            if std::env::var("VERBOSE").is_ok() {
                eprintln!("Completed in {:.2}ms", start_time.elapsed().as_millis());
            }
            Ok(())
        }
        Err(e) => {
            eprintln!("Error: {}", e);
            
            // Print helpful error context
            match &e {
                SSRError::FileNotFound(path) => {
                    eprintln!("Make sure the file exists: {}", path.display());
                }
                SSRError::JsRuntime(msg) => {
                    eprintln!("Try using --compile-type debug to see the compiled output");
                    eprintln!("Runtime error details: {}", msg);
                }
                SSRError::ParseError(msg) => {
                    eprintln!("Check your TSX syntax in the component files");
                    eprintln!("Parse error details: {}", msg);
                }
                _ => {}
            }
            
            std::process::exit(1);
        }
    }
}

async fn run() -> Result<(), SSRError> {
    let config = parse_args()?;
    
    if config.verbose {
        eprintln!("Starting SSR bundler...");
        eprintln!("Route: {}", config.route);
        eprintln!("App dir: {}", config.app_dir.display());
        eprintln!("Compile type: {:?}", config.compile_type);
    }

    // Validate inputs
    validate_config(&config)?;

    // Handle debug mode separately
    if matches!(config.compile_type, CompileType::Debug) {
        return handle_debug_mode(&config).await;
    }

    // Initialize components
    let compiler = TSXCompiler::new()?;
    let layout_resolver = LayoutResolver::new(config.app_dir.clone());
    let renderer = SSRRenderer::new()?;

    // Resolve layouts for the route
    let layouts = layout_resolver.resolve_layouts(&config.route)?;
    
    if config.verbose {
        eprintln!("Found {} layout(s)", layouts.len());
        for layout in &layouts {
            eprintln!("- {}", layout.display());
        }
    }

    // Compile and render based on type
    let result = match config.compile_type {
        CompileType::Ssr => handle_ssr(&compiler, &renderer, &config, &layouts).await?,
        CompileType::Hydration => handle_hydration(&compiler, &renderer, &config, &layouts).await?,
        CompileType::Static => handle_static(&compiler, &renderer, &config, &layouts).await?,
        CompileType::Debug => unreachable!(), // Handled above
    };

    // Output result
    output_result(&result, &config)?;

    Ok(())
}

fn parse_args() -> Result<Config, SSRError> {
    let matches = Command::new("ssr-bundler")
        .version("1.0")
        .about("High-performance TSX SSR bundler for Tavo framework")
        .arg(
            Arg::new("route")
                .long("route")
                .short('r')
                .value_name("ROUTE")
                .help("Route to render (e.g., /dashboard, /users/[id])")
                .required(true),
        )
        .arg(
            Arg::new("app-dir")
                .long("app-dir")
                .short('a')
                .value_name("DIR")
                .help("App directory path containing page.tsx files")
                .required(true),
        )
        .arg(
            Arg::new("compile-type")
                .long("compile-type")
                .short('c')
                .value_name("TYPE")
                .help("Compile type: ssr, hydration, static, or debug")
                .default_value("ssr"),
        )
        .arg(
            Arg::new("output")
                .long("output")
                .short('o')
                .value_name("FORMAT")
                .help("Output format: json, text, or html")
                .default_value("json"),
        )
        .arg(
            Arg::new("verbose")
                .long("verbose")
                .short('v')
                .help("Enable verbose output")
                .action(clap::ArgAction::SetTrue),
        )
        .arg(
            Arg::new("minify")
                .long("minify")
                .help("Minify the output JavaScript")
                .action(clap::ArgAction::SetTrue),
        )
        .arg(
            Arg::new("source-maps")
                .long("source-maps")
                .help("Generate source maps")
                .action(clap::ArgAction::SetTrue),
        )
        .get_matches();

    Ok(Config {
        route: matches.get_one::<String>("route").unwrap().clone(),
        app_dir: PathBuf::from(matches.get_one::<String>("app-dir").unwrap()),
        compile_type: matches.get_one::<String>("compile-type").unwrap().parse()?,
        output_format: matches.get_one::<String>("output").unwrap().parse()?,
        verbose: matches.get_flag("verbose"),
        minify: matches.get_flag("minify"),
        source_maps: matches.get_flag("source-maps"),
    })
}

fn validate_config(config: &Config) -> Result<(), SSRError> {
    // Validate app directory exists
    if !config.app_dir.exists() {
        return Err(SSRError::FileNotFound(config.app_dir.clone()));
    }

    if !config.app_dir.is_dir() {
        return Err(SSRError::InvalidPath(format!(
            "App directory is not a directory: {}",
            config.app_dir.display()
        )));
    }

    // Validate route format
    if !config.route.starts_with('/') {
        return Err(SSRError::InvalidRoute(format!(
            "Route must start with '/': {}",
            config.route
        )));
    }

    // Check if page.tsx exists for the route
    let page_path = resolve_page_path(&config.app_dir, &config.route)?;
    if !page_path.exists() {
        return Err(SSRError::FileNotFound(page_path));
    }

    Ok(())
}

fn resolve_page_path(app_dir: &PathBuf, route: &str) -> Result<PathBuf, SSRError> {
    let mut path = app_dir.clone();
    
    if route != "/" {
        let segments: Vec<&str> = route
            .trim_start_matches('/')
            .split('/')
            .filter(|s| !s.is_empty())
            .collect();
            
        for segment in segments {
            path.push(segment);
        }
    }
    
    path.push("page.tsx");
    Ok(path)
}

async fn handle_ssr(
    compiler: &TSXCompiler,
    renderer: &SSRRenderer,
    config: &Config,
    layouts: &[PathBuf],
) -> Result<Value, SSRError> {
    let compiled = compiler.compile_route_with_layouts(&config.route, layouts).await?;
    
    let html = match renderer.render_to_html(&compiled).await {
        Ok(html) => html,
        Err(e) => {
            if config.verbose {
                eprintln!("SSR failed, falling back to simple renderer: {}", e);
            }
            // Fallback to simple renderer for debugging
            let simple_renderer = SimpleSSRRenderer::new();
            simple_renderer.render_component_simple(&compiled).await?
        }
    };

    Ok(json!({
        "html": html,
        "js": null,
        "type": "ssr",
        "route": config.route,
        "layouts": layouts.iter().map(|p| p.display().to_string()).collect::<Vec<_>>()
    }))
}

async fn handle_hydration(
    compiler: &TSXCompiler,
    renderer: &SSRRenderer,
    config: &Config,
    layouts: &[PathBuf],
) -> Result<Value, SSRError> {
    let compiled = compiler.compile_route_with_layouts(&config.route, layouts).await?;
    
    let html = match renderer.render_to_html(&compiled).await {
        Ok(html) => html,
        Err(e) => {
            if config.verbose {
                eprintln!("SSR failed, using fallback HTML: {}", e);
            }
            let simple_renderer = SimpleSSRRenderer::new();
            simple_renderer.render_component_simple(&compiled).await?
        }
    };
    
    let js = compiler.compile_for_hydration(&compiled).await?;

    Ok(json!({
        "html": html,
        "js": js,
        "type": "hydration",
        "route": config.route,
        "layouts": layouts.iter().map(|p| p.display().to_string()).collect::<Vec<_>>()
    }))
}

async fn handle_static(
    compiler: &TSXCompiler,
    renderer: &SSRRenderer,
    config: &Config,
    layouts: &[PathBuf],
) -> Result<Value, SSRError> {
    let compiled = compiler.compile_route_with_layouts(&config.route, layouts).await?;
    
    let html = match renderer.render_to_static_html(&compiled).await {
        Ok(html) => html,
        Err(e) => {
            if config.verbose {
                eprintln!("Static render failed, using fallback: {}", e);
            }
            let simple_renderer = SimpleSSRRenderer::new();
            simple_renderer.render_component_simple(&compiled).await?
        }
    };

    Ok(json!({
        "html": html,
        "js": null,
        "type": "static",
        "route": config.route,
        "layouts": layouts.iter().map(|p| p.display().to_string()).collect::<Vec<_>>()
    }))
}

async fn handle_debug_mode(config: &Config) -> Result<(), SSRError> {
    if config.verbose {
        eprintln!("Debug mode enabled");
    }

    let layout_resolver = LayoutResolver::new(config.app_dir.clone());
    let layouts = layout_resolver.resolve_layouts(&config.route)?;
    
    // Debug information
    let debug_info = json!({
        "config": {
            "route": config.route,
            "app_dir": config.app_dir.display().to_string(),
            "compile_type": format!("{:?}", config.compile_type),
            "output_format": format!("{:?}", config.output_format),
            "minify": config.minify,
            "source_maps": config.source_maps,
        },
        "discovered_layouts": layouts.iter().map(|p| p.display().to_string()).collect::<Vec<_>>(),
        "page_path": resolve_page_path(&config.app_dir, &config.route)?.display().to_string(),
        "timestamp": std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
    });

    // Try to compile without rendering to check for compilation errors
    let compiler = TSXCompiler::new()?;
    match compiler.compile_route_with_layouts(&config.route, &layouts).await {
        Ok(compiled) => {
            println!("{}", serde_json::to_string_pretty(&json!({
                "status": "success",
                "debug_info": debug_info,
                "compiled_component": {
                    "route": compiled.route,
                    "layouts_count": compiled.layouts.len(),
                    "page_component_size": compiled.page_component.len(),
                    "combined_js_size": compiled.combined_js.len(),
                    "layouts": compiled.layouts.iter().map(|l| json!({
                        "path": l.path.display().to_string(),
                        "component_name": l.component_name,
                        "js_size": l.compiled_js.len()
                    })).collect::<Vec<_>>()
                }
            }))?);
        }
        Err(e) => {
            println!("{}", serde_json::to_string_pretty(&json!({
                "status": "compilation_error",
                "error": e.to_string(),
                "debug_info": debug_info,
            }))?);
        }
    }

    Ok(())
}

fn output_result(result: &Value, config: &Config) -> Result<(), SSRError> {
    match config.output_format {
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(result)
                .map_err(|e| SSRError::SerializationError(e.to_string()))?);
        }
        OutputFormat::Text => {
            if let Some(html) = result.get("html") {
                if let Some(html_str) = html.as_str() {
                    println!("{}", html_str);
                } else {
                    return Err(SSRError::InvalidOutput("HTML field is not a string".to_string()));
                }
            } else {
                return Err(SSRError::InvalidOutput("No HTML field in result".to_string()));
            }
        }
        OutputFormat::Html => {
            if let Some(html) = result.get("html") {
                if let Some(html_str) = html.as_str() {
                    // Wrap in a complete HTML document if it's just a fragment
                    if !html_str.trim_start().starts_with("<!DOCTYPE") {
                        println!("<!DOCTYPE html>\n<html><head><title>Tavo App</title></head><body>{}</body></html>", html_str);
                    } else {
                        println!("{}", html_str);
                    }
                } else {
                    return Err(SSRError::InvalidOutput("HTML field is not a string".to_string()));
                }
            } else {
                return Err(SSRError::InvalidOutput("No HTML field in result".to_string()));
            }
        }
    }

    Ok(())
}