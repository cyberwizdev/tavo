// Mock React for SSR environment
const React = {
  createElement: function(type, props, ...children) {
    return {
      type,
      props: props || {},
      children: children.filter(child => child != null)
    };
  },
  
  Fragment: function(props) {
    return props.children;
  },
  
  useState: function(initialState) {
    return [initialState, function() {}];
  },
  
  useEffect: function() {
    // No-op in SSR
  },
  
  useParams: function() {
    return this.__PARAMS__ || {};
  }
};

this.React = React;