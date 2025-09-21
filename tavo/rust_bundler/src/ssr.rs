use anyhow::{Result, Context};
use boa_engine::{Context as BoaContext, Source};
use std::collections::HashMap;

use crate::bundler::Bundle;

pub struct SSRRenderer {
    context: BoaContext,
}

impl SSRRenderer {
    pub fn new() -> Result<Self> {
        let mut context = BoaContext::default();
        
        // Setup React and ReactDOMServer globals
        Self::setup_react_globals(&mut context)?;
        
        Ok(Self { context })
    }
    
    pub async fn render(&mut self, bundle: &Bundle) -> Result<String> {
        // Execute all modules in dependency order
        for (module_path, code) in &bundle.modules {
            if module_path != &bundle.entry_point {
                self.execute_module(module_path, code)?;
            }
        }
        
        // Execute entry point and render
        if let Some(entry_code) = bundle.modules.get(&bundle.entry_point) {
            self.execute_module(&bundle.entry_point, entry_code)?;
            self.render_to_string()
        } else {
            Err(anyhow::anyhow!("Entry point not found in bundle"))
        }
    }
    
    fn execute_module(&mut self, _module_path: &str, code: &str) -> Result<()> {
        self.context
            .eval(Source::from_bytes(code))
            .map_err(|e| anyhow::anyhow!("JavaScript execution error: {}", e))?;
        
        Ok(())
    }
    
    fn render_to_string(&mut self) -> Result<String> {
        let render_script = r#"
            (function() {
                try {
                    // Assume the last exported component is the App
                    const App = typeof module !== 'undefined' && module.exports 
                        ? module.exports.default || module.exports
                        : window.App;
                    
                    if (!App) {
                        throw new Error('No App component found');
                    }
                    
                    const element = React.createElement(App);
                    return ReactDOMServer.renderToString(element);
                } catch (error) {
                    return '<div>Error rendering component: ' + error.message + '</div>';
                }
            })()
        "#;
        
        let result = self.context
            .eval(Source::from_bytes(render_script))
            .context("Failed to render component to string")?;
        
        result
            .to_string(&mut self.context)
            .map(|s| s.to_std_string_escaped())
            .context("Failed to convert render result to string")
    }
    
    fn setup_react_globals(context: &mut BoaContext) -> Result<()> {
        // Mock React implementation for SSR
        let react_mock = r#"
            window.React = {
                createElement: function(type, props, ...children) {
                    if (typeof type === 'string') {
                        // HTML element
                        let attrs = '';
                        if (props) {
                            for (let key in props) {
                                if (key !== 'children' && props[key] != null) {
                                    if (key === 'className') {
                                        attrs += ` class="${props[key]}"`;
                                    } else {
                                        attrs += ` ${key}="${props[key]}"`;
                                    }
                                }
                            }
                        }
                        
                        const allChildren = props && props.children 
                            ? [].concat(props.children, children).filter(Boolean)
                            : children.filter(Boolean);
                        
                        if (allChildren.length === 0) {
                            return `<${type}${attrs} />`;
                        }
                        
                        const childrenStr = allChildren
                            .map(child => typeof child === 'string' ? child : child.toString())
                            .join('');
                        
                        return `<${type}${attrs}>${childrenStr}</${type}>`;
                    } else if (typeof type === 'function') {
                        // Component
                        const allChildren = props && props.children 
                            ? [].concat(props.children, children).filter(Boolean)
                            : children.filter(Boolean);
                        
                        const finalProps = { ...props };
                        if (allChildren.length > 0) {
                            finalProps.children = allChildren.length === 1 ? allChildren[0] : allChildren;
                        }
                        
                        return type(finalProps);
                    }
                    return '';
                },
                Fragment: function(props) {
                    return props.children || '';
                }
            };
            
            window.ReactDOMServer = {
                renderToString: function(element) {
                    if (typeof element === 'string') {
                        return element;
                    }
                    if (typeof element === 'object' && element.toString) {
                        return element.toString();
                    }
                    return String(element);
                }
            };
        "#;
        
        context
            .eval(Source::from_bytes(react_mock))
            .context("Failed to setup React globals")?;
        
        Ok(())
    }
}