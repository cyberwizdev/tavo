// Mock ReactDOMServer for SSR environment
const ReactDOMServer = {
  renderToString: function(element) {
    function renderElement(el) {
      if (typeof el === 'string' || typeof el === 'number') {
        return String(el);
      }
      
      if (!el || typeof el !== 'object') {
        return '';
      }
      
      if (Array.isArray(el)) {
        return el.map(renderElement).join('');
      }
      
      const { type, props = {}, children = [] } = el;
      
      if (typeof type === 'string') {
        // HTML element
        const attrs = Object.entries(props)
          .filter(([key]) => key !== 'children')
          .map(([key, value]) => {
            if (key === 'className') key = 'class';
            return `${key}="${value}"`;
          })
          .join(' ');
        
        const childrenHtml = children.map(renderElement).join('');
        
        if (['br', 'hr', 'img', 'input', 'meta', 'link'].includes(type)) {
          return `<${type}${attrs ? ' ' + attrs : ''} />`;
        }
        
        return `<${type}${attrs ? ' ' + attrs : ''}>${childrenHtml}</${type}>`;
      } else if (typeof type === 'function') {
        // React component
        const childProps = { ...props, children };
        return renderElement(type(childProps));
      }
      
      return '';
    }
    
    return renderElement(element);
  }
};

this.ReactDOMServer = ReactDOMServer;