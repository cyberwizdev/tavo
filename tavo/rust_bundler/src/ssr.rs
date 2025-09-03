use anyhow::{anyhow, Result};
use rquickjs::{Context, Runtime};
use std::collections::HashMap;
use std::time::Duration;
use tokio::time::timeout;

pub async fn render_to_string(
    transpiled_code: &str,
    params: &HashMap<String, String>,
    timeout_ms: u64,
) -> Result<String> {
    let timeout_duration = Duration::from_millis(timeout_ms);
    
    timeout(timeout_duration, async {
        render_to_string_inner(transpiled_code, params).await
    })
    .await
    .map_err(|_| anyhow!("SSR rendering timed out after {}ms", timeout_ms))?
}

async fn render_to_string_inner(
    transpiled_code: &str,
    params: &HashMap<String, String>,
) -> Result<String> {
    let runtime = Runtime::new()?;
    let context = Context::full(&runtime)?;
    
    context.with(|ctx| -> Result<String> {
        // Set up React and ReactDOMServer
        let react_code = include_str!("../runtime/react.js");
        let react_dom_server_code = include_str!("../runtime/react-dom-server.js");
        
        // Execute React setup
        ctx.eval::<(), _>(react_code)
            .map_err(|e| anyhow!("Failed to load React: {}", e))?;
            
        ctx.eval::<(), _>(react_dom_server_code)
            .map_err(|e| anyhow!("Failed to load ReactDOMServer: {}", e))?;
        
        // Execute the transpiled user code
        ctx.eval::<(), _>(transpiled_code)
            .map_err(|e| anyhow!("Failed to execute user code: {}", e))?;
        
        // Create params object
        let params_json = serde_json::to_string(params)?;
        
        // Execute SSR rendering
        let render_script = format!(
            r#"
            const App = this.default || this.App;
            const params = {};
            const element = React.createElement(App, {{ params }});
            ReactDOMServer.renderToString(element);
            "#,
            params_json
        );
        
        let html: String = ctx.eval(&render_script)
            .map_err(|e| anyhow!("SSR rendering failed: {}", e))?;
            
        Ok(html)
    })
}