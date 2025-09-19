"""
HTML templates and HMR client scripts
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .constants import (
    SSR_HTML_PLACEHOLDER, INITIAL_STATE_PLACEHOLDER, 
    CLIENT_BUNDLE_PLACEHOLDER, HMR_SCRIPT_PLACEHOLDER
)

logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages HTML templates and client scripts"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self._base_template: Optional[str] = None
        self._error_template: Optional[str] = None
    
    def get_base_template(self) -> str:
        """Get the base HTML template"""
        if self._base_template is None:
            # Try to load custom template from project
            custom_template = self.project_root / "templates" / "base.html"
            
            if custom_template.exists():
                try:
                    with open(custom_template, 'r', encoding='utf-8') as f:
                        self._base_template = f.read()
                    logger.info("Loaded custom base template")
                except Exception as e:
                    logger.warning(f"Failed to load custom template: {e}")
                    self._base_template = self._get_default_template()
            else:
                self._base_template = self._get_default_template()
        
        return self._base_template
    
    def _get_default_template(self) -> str:
        """Get the default HTML template"""
        return '''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Tavo App</title>
    <meta name="description" content="Built with Tavo framework">
    <link rel="icon" type="image/x-icon" href="/public/favicon.ico">
</head>
<body>
    <div id="root">''' + SSR_HTML_PLACEHOLDER + '''</div>
    <script>
        window.__INITIAL_PROPS__ = ''' + INITIAL_STATE_PLACEHOLDER + ''';
        window.__TAVO_ENV__ = "development";
    </script>
    <script src="''' + CLIENT_BUNDLE_PLACEHOLDER + '''" defer></script>
    ''' + HMR_SCRIPT_PLACEHOLDER + '''
</body>
</html>'''
    
    def get_error_template(self) -> str:
        """Get the error page template"""
        if self._error_template is None:
            custom_error = self.project_root / "templates" / "error.html"
            
            if custom_error.exists():
                try:
                    with open(custom_error, 'r', encoding='utf-8') as f:
                        self._error_template = f.read()
                    logger.info("Loaded custom error template")
                except Exception as e:
                    logger.warning(f"Failed to load custom error template: {e}")
                    self._error_template = self._get_default_error_template()
            else:
                self._error_template = self._get_default_error_template()
        
        return self._error_template
    
    def _get_default_error_template(self) -> str:
        """Get the default error template"""
        return '''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Error - Tavo App</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        .error-container {
            background: #f8f9fa;
            border-left: 4px solid #dc3545;
            padding: 2rem;
            border-radius: 4px;
            margin: 2rem 0;
        }
        .error-title {
            color: #dc3545;
            margin: 0 0 1rem 0;
            font-size: 1.5rem;
        }
        .error-message {
            background: white;
            padding: 1rem;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        .back-link {
            display: inline-block;
            margin-top: 1rem;
            color: #007bff;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1 class="error-title">Application Error</h1>
        <div class="error-message">%%ERROR_MESSAGE%%</div>
        <a href="/" class="back-link">← Back to Home</a>
    </div>
    <script>
        // Auto-reload in development when error is fixed
        if (window.__TAVO_ENV__ === "development") {
            setTimeout(() => {
                console.log("Attempting to reload...");
                window.location.reload();
            }, 2000);
        }
    </script>
</body>
</html>'''
    
    def render_html(self, ssr_html: str, state: Dict[str, Any], client_script_path: str) -> str:
        """
        Render complete HTML page
        
        Args:
            ssr_html: Server-side rendered HTML content
            state: Initial application state
            client_script_path: Path to client bundle
            
        Returns:
            Complete HTML document
        """
        template = self.get_base_template()
        
        # Replace placeholders
        html = template.replace(SSR_HTML_PLACEHOLDER, ssr_html)
        html = html.replace(INITIAL_STATE_PLACEHOLDER, json.dumps(state))
        html = html.replace(CLIENT_BUNDLE_PLACEHOLDER, client_script_path)
        html = html.replace(HMR_SCRIPT_PLACEHOLDER, "")  # Will be filled by inject_hmr_script if needed
        
        return html
    
    def render_error_page(self, error_message: str) -> str:
        """
        Render error page
        
        Args:
            error_message: Error message to display
            
        Returns:
            Error HTML page
        """
        template = self.get_error_template()
        return template.replace("%%ERROR_MESSAGE%%", error_message)
    
    def inject_hmr_script(self, html: str) -> str:
        """
        Inject HMR client script into HTML
        
        Args:
            html: HTML content to inject script into
            
        Returns:
            HTML with HMR script injected
        """
        hmr_script = self._get_hmr_client_script()
        
        if HMR_SCRIPT_PLACEHOLDER in html:
            return html.replace(HMR_SCRIPT_PLACEHOLDER, hmr_script)
        else:
            # Fallback: inject before closing body tag
            return html.replace("</body>", f"{hmr_script}\n</body>")
    
    def _get_hmr_client_script(self) -> str:
        """Get HMR client script"""
        # This is a simplified HMR client - in production would be more sophisticated
        return f'''
    <script>
        // Tavo HMR Client
        
    </script>'''
    
    def render_loading_page(self, message: str = "Loading...") -> str:
        """Render a loading page"""
        return f'''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Loading - Tavo App</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f8f9fa;
        }}
        .loader {{
            text-align: center;
        }}
        .spinner {{
            border: 4px solid #e9ecef;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="loader">
        <div class="spinner"></div>
        <p>{message}</p>
    </div>
</body>
</html>'''