use log::LevelFilter;

pub fn setup_logging(level: &str) {
    let log_level = match level {
        "error" => LevelFilter::Error,
        "warn" => LevelFilter::Warn,
        "info" => LevelFilter::Info,
        "debug" => LevelFilter::Debug,
        "trace" => LevelFilter::Trace,
        _ => LevelFilter::Warn,
    };
    
    env_logger::Builder::from_default_env()
        .filter_level(log_level)
        .init();
}

pub fn normalize_route(route: &str) -> String {
    if route.is_empty() || route == "/" {
        return "/".to_string();
    }
    
    let mut normalized = route.to_string();
    if !normalized.starts_with('/') {
        normalized = format!("/{}", normalized);
    }
    
    // Remove trailing slash except for root
    if normalized.len() > 1 && normalized.ends_with('/') {
        normalized.pop();
    }
    
    normalized
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_normalize_route() {
        assert_eq!(normalize_route(""), "/");
        assert_eq!(normalize_route("/"), "/");
        assert_eq!(normalize_route("about"), "/about");
        assert_eq!(normalize_route("/about"), "/about");
        assert_eq!(normalize_route("/about/"), "/about");
        assert_eq!(normalize_route("blog/post/"), "/blog/post");
    }
}