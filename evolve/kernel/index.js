// kernel/index.js
// Minimal Evolve Kernel — exposes APIs to WASM / Python.
// Attach to window.EvolveKernel

const EvolveKernel = (function () {
  // internal node registry (maps nodeId -> DOM node)
  const nodes = new Map();
  let nextNodeId = 1;

  // callback registry for WASM/Python to register functions
  const callbacks = new Map();
  let nextCallbackId = 1;

  function genNodeId() { return nextNodeId++; }
  function genCallbackId() { return nextCallbackId++; }

  // Logger
  function log(level, message) {
    const payload = { ts: Date.now(), level, message };
    console[level === 'error' ? 'error' : 'log']('[Kernel]', payload);
    return { ok:true };
  }

  // DOM helpers
  function create(tag, props = {}, children = []) {
    try {
      const el = document.createElement(tag);
      applyProps(el, props);
      const id = genNodeId();
      nodes.set(id, el);
      // attach children if any (children can be nodeIds or strings)
      for (const child of children) {
        if (typeof child === 'number') {
          const childNode = nodes.get(child);
          if (childNode) el.appendChild(childNode);
        } else {
          el.appendChild(document.createTextNode(String(child)));
        }
      }
      return { ok: true, value: id };
    } catch (e) {
      return { ok:false, error: e.message };
    }
  }

  function applyProps(el, props) {
    for (const [k,v] of Object.entries(props)) {
      if (k === 'style' && typeof v === 'object') {
        Object.assign(el.style, v);
      } else if (k.startsWith('on') && typeof v === 'string') {
        // v should be callbackId string from WASM/Python
        // We'll attach an event listener that calls kernel.async.call(callbackId, [eventData])
        const eventName = k.slice(2).toLowerCase();
        const cbId = Number(v);
        el.addEventListener(eventName, (ev) => {
          const eventData = { type: ev.type, targetId: findNodeId(el) };
          asyncCall(cbId, [eventData]);
        });
      } else if (k === 'textContent') {
        el.textContent = v;
      } else {
        el.setAttribute(k, v);
      }
    }
  }

  function findNodeId(node) {
    for (const [id, n] of nodes.entries()) if (n === node) return id;
    return null;
  }

  function update(nodeId, props = {}) {
    const el = nodes.get(nodeId);
    if (!el) return { ok:false, error: 'no-such-node' };
    try {
      applyProps(el, props);
      return { ok:true, value: nodeId };
    } catch(e) {
      return { ok:false, error: e.message };
    }
  }

  function append(parentId, nodeId) {
    const parent = nodes.get(parentId);
    const child = nodes.get(nodeId);
    if (!parent || !child) return { ok:false, error: 'invalid-node' };
    parent.appendChild(child);
    return { ok:true };
  }

  function query(selector) {
    const el = document.querySelector(selector);
    if (!el) return { ok:true, value: null };
    const id = findNodeId(el) || (function(){
      // register external node
      const nid = genNodeId();
      nodes.set(nid, el);
      return nid;
    })();
    return { ok:true, value: id };
  }

  // Async/callback bridge
  function registerCallback(fn) {
    const id = genCallbackId();
    callbacks.set(id, fn);
    return { ok:true, value: id };
  }

  function unregisterCallback(id) {
    callbacks.delete(Number(id));
    return { ok:true };
  }

  async function asyncCall(cbId, args = []) {
    const fn = callbacks.get(Number(cbId));
    if (!fn) {
      console.warn('Kernel: missing callback', cbId);
      return { ok:false, error: 'missing-callback' };
    }
    try {
      // Allow callbacks that return promises
      const result = await Promise.resolve(fn(...args));
      return { ok:true, value: result };
    } catch (e) {
      return { ok:false, error: e.message };
    }
  }

  // FS (simple in-memory for prototype)
  const fs = new Map();
  function fs_read(path) {
    return { ok:true, value: fs.get(path) ?? null };
  }
  function fs_write(path, contents) {
    fs.set(path, contents);
    return { ok:true };
  }

  // net.fetch wrapper
  async function net_fetch(url, options = {}) {
    try {
      const res = await fetch(url, options);
      const text = await res.text();
      return { ok:true, value: { status: res.status, headers: Object.fromEntries(res.headers.entries()), body: text } };
    } catch (e) {
      return { ok:false, error: e.message };
    }
  }

  // Public API
  return {
    log,
    dom: { create, update, append, query },
    registerCallback, unregisterCallback, asyncCall,
    fs: { read: fs_read, write: fs_write },
    net: { fetch: net_fetch },
    _internal: { nodes } // for debugging in dev only
  };
})();

// attach to window
window.EvolveKernel = EvolveKernel;
console.log('[Kernel] initialized');
