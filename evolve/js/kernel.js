// Minimal Evolve Kernel - exposes APIs to WASM / Python.
// Attached to window.EvolveKernel

const EvolveKernel = (function () {
  // internal node registry (maps nodeId -> DOM node)
  const nodes = new Map();
  let nextNodeId = 1;

  // callback registry for WASM/Python to register functions
  const callbacks = new Map();
  let nextCallbackId = 1;

  function genNodeId() {
    return nextNodeId++;
  }
  function genCallbackId() {
    return nextCallbackId++;
  }

  // Logger
  function log(level, message) {
    const payload = { ts: Date.now(), level, message };
    console[level === "error" ? "error" : "log"]("[Kernel]", payload);
    return { ok: true };
  }

  // -------------------------
  // TEXT NODE SUPPORT
  // -------------------------

  function createText(nodeIdOrText, maybeText) {
    try {
      let nodeId;
      let text;

      if (typeof maybeText === "undefined") {
        // createText("hello")
        text = String(nodeIdOrText ?? "");
        nodeId = genNodeId();
      } else {
        // createText(10, "hello")
        nodeId = Number(nodeIdOrText);
        text = String(maybeText ?? "");
      }

      const tnode = document.createTextNode(text);
      tnode.__evolve_id = nodeId;
      nodes.set(nodeId, tnode);

      return { ok: true, value: nodeId };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function setText(nodeId, text) {
    try {
      const node = nodes.get(Number(nodeId));
      if (!node) return { ok: false, error: "no-such-node" };

      if (node.nodeType === Node.TEXT_NODE) {
        node.nodeValue = String(text ?? "");
      } else {
        node.textContent = String(text ?? "");
      }

      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  // -------------------------
  // DOM ELEMENT CREATE
  // -------------------------

  function create(tag, props = {}, children = []) {
    try {
      const el = document.createElement(tag);
      applyProps(el, props);

      const id = genNodeId();
      nodes.set(id, el);
      el.__evolve_id = id;

      for (const child of children) {
        if (typeof child === "number") {
          const childNode = nodes.get(child);
          if (childNode) el.appendChild(childNode);
        } else {
          // register string children as text nodes
          const tid = genNodeId();
          const textNode = document.createTextNode(String(child));
          textNode.__evolve_id = tid;
          nodes.set(tid, textNode);
          el.appendChild(textNode);
        }
      }

      return { ok: true, value: id };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function remove(nodeID) {
    try {
      const node = nodes.get(nodeID);

      if (!node) {
        return { ok: false, error: "Node not found" };
      }

      const children = Array.from(node.childNodes || []);
      for (const child of children) {
        const childId = findNodeId(child);
        if (childId) {
          remove(childId);
        } else {
          child.remove();
        }
      }

      if (node.parentNode) {
        node.parentNode.removeChild(node);
      }

      nodes.delete(nodeID);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function insertAt(parentId, nodeId, index) {
    try {
      const parent = nodes.get(parentId);
      const child = nodes.get(nodeId);

      if (!parent || !child) {
        return { ok: false, error: "insertAt: invalid-node" };
      }

      const children = parent.childNodes;
      const refNode =
        index >= 0 && index < children.length ? children[index] : null;

      parent.insertBefore(child, refNode);
      child.__evolve_parent = parentId;

      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function applyProps(el, props) {
    for (const [k, v] of Object.entries(props)) {
      if (k === "style" && typeof v === "object") {
        Object.assign(el.style, v);
      } else if (k.startsWith("on") && typeof v === "string") {
        const eventName = k.slice(2).toLowerCase();
        const cbId = Number(v);
        el.addEventListener(eventName, (ev) => {
          const eventData = { type: ev.type, targetId: findNodeId(el) };
          asyncCall(cbId, [eventData]);
        });
      } else if (k === "textContent") {
        el.textContent = v;
      } else {
        el.setAttribute(k, v);
      }
    }
  }

  function findNodeId(node) {
    return node.__evolve_id || null;
  }

  function update(nodeId, props = {}) {
    const el = nodes.get(nodeId);
    if (!el) return { ok: false, error: "no-such-node" };
    try {
      applyProps(el, props);
      return { ok: true, value: nodeId };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function append(parentId, nodeId) {
    const parent = nodes.get(parentId);
    const child = nodes.get(nodeId);

    if (!parent || !child) return { ok: false, error: "invalid-node" };

    parent.appendChild(child);
    child.__evolve_parent = parentId;

    return { ok: true };
  }

  function query(selector) {
    const el = document.querySelector(selector);
    if (!el) return { ok: true, value: null };
    const id =
      findNodeId(el) ||
      (function () {
        const nid = genNodeId();
        nodes.set(nid, el);
        el.__evolve_id = nid;
        return nid;
      })();
    return { ok: true, value: id };
  }

  // Async bridge
  function registerCallback(fn) {
    const id = genCallbackId();
    callbacks.set(id, fn);
    return { ok: true, value: id };
  }

  function unregisterCallback(id) {
    callbacks.delete(Number(id));
    return { ok: true };
  }

  async function asyncCall(cbId, args = []) {
    const fn = callbacks.get(Number(cbId));
    if (!fn) {
      console.warn("Kernel: missing callback", cbId);
      return { ok: false, error: "missing-callback" };
    }
    try {
      const result = await Promise.resolve(fn(...args));
      return { ok: true, value: result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  const fs = new Map();

  function fs_read(path) {
    return { ok: true, value: fs.get(path) ?? null };
  }
  function fs_write(path, contents) {
    fs.set(path, contents);
    return { ok: true };
  }

  async function net_fetch(url, options = {}) {
    try {
      const res = await fetch(url, options);
      const text = await res.text();
      return {
        ok: true,
        value: {
          status: res.status,
          headers: Object.fromEntries(res.headers.entries()),
          body: text,
        },
      };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  const location = {
    getPath() {
      return window.location.pathname;
    },
    push(path) {
      if (typeof path !== "string")
        return { ok: false, error: "path must be string" };
      window.history.pushState({}, "", path);
      return { ok: true };
    },
    replace(path) {
      if (typeof path !== "string")
        return { ok: false, error: "path must be string" };
      window.history.replaceState({}, "", path);
      return { ok: true };
    },
    onChange(cbId) {
      const id = Number(cbId);
      if (!callbacks.has(id))
        return { ok: false, error: "Callback not found" };

      window.addEventListener("popstate", () => {
        const fn = callbacks.get(id);
        if (fn) fn();
      });
      return { ok: true };
    },
    forward() {
      window.history.forward();
      return { ok: true };
    },
    back() {
      window.history.back();
      return { ok: true };
    },
  };

  // Public API
  return {
    log,
    dom: {
      create,
      createText,
      setText,
      remove,
      insertAt,
      update,
      append,
      query,
    },
    location,
    registerCallback,
    unregisterCallback,
    asyncCall,
    fs: { read: fs_read, write: fs_write },
    net: { fetch: net_fetch },
    _internal: { nodes },
  };
})();

window.EvolveKernel = EvolveKernel;
console.log("[Kernel] initialized");
