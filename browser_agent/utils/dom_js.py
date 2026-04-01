"""JavaScript snippets injected via Runtime.evaluate for DOM extraction.

All JS is written as immediately-invoked expressions that return serialisable
plain objects — no Promises, no DOM references.
"""

# ---------------------------------------------------------------------------
# Primary DOM extraction script
# ---------------------------------------------------------------------------
# Returns a JSON-serialisable array of element descriptors.
# Injected once per extraction cycle via a single Runtime.evaluate call.

DOM_EXTRACT_JS = r"""
(() => {
  // ---- helpers -----------------------------------------------------------

  function computeCssSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE) {
      let seg = cur.tagName.toLowerCase();
      if (cur.id) {
        seg = '#' + CSS.escape(cur.id);
        parts.unshift(seg);
        break;
      }
      const siblings = Array.from(cur.parentNode ? cur.parentNode.children : [])
        .filter(s => s.tagName === cur.tagName);
      if (siblings.length > 1) {
        const idx = siblings.indexOf(cur) + 1;
        seg += ':nth-of-type(' + idx + ')';
      }
      parts.unshift(seg);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }

  function computeXPath(el) {
    if (el.id) return '//*[@id="' + el.id + '"]';
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === Node.ELEMENT_NODE) {
      const tag = cur.tagName.toLowerCase();
      const siblings = Array.from(cur.parentNode ? cur.parentNode.children : [])
        .filter(s => s.tagName === cur.tagName);
      const idx = siblings.length > 1 ? '[' + (siblings.indexOf(cur) + 1) + ']' : '';
      parts.unshift(tag + idx);
      cur = cur.parentElement;
    }
    return '/' + parts.join('/');
  }

  function nearestParentText(el) {
    let cur = el.parentElement;
    while (cur) {
      const t = (cur.innerText || '').trim().slice(0, 80);
      if (t) return t;
      cur = cur.parentElement;
    }
    return null;
  }

  function isVisible(el) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return false;
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }

  // ---- main --------------------------------------------------------------

  const QUERY = 'a,button,input,select,textarea,[role=button],[role=link],[tabindex]';
  const els = Array.from(document.querySelectorAll(QUERY)).filter(isVisible);

  return els.map((el, i) => {
    const bbox = el.getBoundingClientRect();
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;

    return {
      index: i,
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || null,
      text: (el.innerText || '').trim().slice(0, 80) || null,
      placeholder: el.getAttribute('placeholder') || null,
      aria_label: el.getAttribute('aria-label') || null,
      css_selector: computeCssSelector(el),
      xpath: computeXPath(el),
      bbox: { x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height },
      attributes: attrs,
      parent_text: nearestParentText(el),
    };
  });
})()
"""

# ---------------------------------------------------------------------------
# DOM visible-text summary script
# ---------------------------------------------------------------------------
# Returns a plain string of visible text nodes, deduped, truncated.

DOM_SUMMARY_JS = r"""
(() => {
  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        const p = node.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        const tag = p.tagName.toLowerCase();
        if (['script','style','noscript','head'].includes(tag)) return NodeFilter.FILTER_REJECT;
        const style = window.getComputedStyle(p);
        if (style.display === 'none' || style.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    }
  );
  const chunks = [];
  let node;
  while ((node = walker.nextNode())) {
    const t = node.textContent.trim();
    if (t.length > 2) chunks.push(t);
  }
  return [...new Set(chunks)].join(' ').slice(0, 2000);
})()
"""

# ---------------------------------------------------------------------------
# Element in-viewport check + scroll-into-view
# ---------------------------------------------------------------------------
# Call with Runtime.callFunctionOn or by interpolating the selector.

SCROLL_INTO_VIEW_JS = r"""
(function(selector) {
  const el = document.querySelector(selector);
  if (el) { el.scrollIntoView({behavior:'instant', block:'center'}); return true; }
  return false;
})
"""

# ---------------------------------------------------------------------------
# Set input value + dispatch events (used by 'type' and 'select' actions)
# ---------------------------------------------------------------------------

SET_VALUE_JS = r"""
(function(selector, value) {
  const el = document.querySelector(selector);
  if (!el) return false;
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  );
  if (nativeInputValueSetter) {
    nativeInputValueSetter.set.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
})
"""

# ---------------------------------------------------------------------------
# Select option by value
# ---------------------------------------------------------------------------

SELECT_OPTION_JS = r"""
(function(selector, value) {
  const el = document.querySelector(selector);
  if (!el) return false;
  el.value = value;
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
})
"""

# ---------------------------------------------------------------------------
# DOM hash — fast fingerprint to detect whether DOM changed
# ---------------------------------------------------------------------------

DOM_HASH_JS = r"""
(() => {
  const html = document.body ? document.body.innerHTML : '';
  let h = 0;
  for (let i = 0; i < Math.min(html.length, 5000); i++) {
    h = (Math.imul(31, h) + html.charCodeAt(i)) | 0;
  }
  return String(h);
})()
"""
