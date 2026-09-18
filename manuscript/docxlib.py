"""Safe editing helpers for RefWorks-managed .docx files.

The manuscript's in-text citations are RefWorks Citation Manager structured
document tags (<w:sdt>) whose w:tag carries a JSON payload of reference ids.
The bibliography is generated live by the add-in from those tags, so:

  * deleting an sdt correctly removes that source from the reference list;
  * damaging an sdt breaks the bibliography irrecoverably.

Every helper here therefore treats an sdt as an opaque, immovable node.
"""
import re, copy
import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def iter_blocks(doc):
    for ch in doc.element.body.iterchildren():
        if ch.tag == qn("w:p"):
            yield Paragraph(ch, doc)
        elif ch.tag == qn("w:tbl"):
            yield Table(ch, doc)

def para_children(p):
    """Top-level children of a <w:p> that carry content, in document order."""
    return [c for c in p._p.iterchildren()
            if c.tag in (qn("w:r"), qn("w:sdt"), qn("w:hyperlink"))]

def annotate(p):
    """Paragraph text with each citation replaced by a {C<n>} placeholder."""
    out, n = [], 0
    for c in para_children(p):
        if c.tag == qn("w:sdt"):
            n += 1
            out.append("{C%d}" % n)
        else:
            out.append("".join(t.text or "" for t in c.iter(qn("w:t"))))
    return "".join(out)

def citation_nodes(p):
    return [c for c in para_children(p) if c.tag == qn("w:sdt")]

def _template_run(p):
    """A plain run from this paragraph, to clone for formatting fidelity."""
    for c in para_children(p):
        if c.tag == qn("w:r") and c.find(qn("w:t")) is not None:
            return c
    return None

def set_text(p, new_text):
    """Replace a paragraph's text.

    `new_text` may contain {C1}, {C2}, ... placeholders referring to the
    citations already present in this paragraph, in their original order.
    Those sdt nodes are re-inserted unchanged; every other child is rebuilt
    from a cloned run so direct formatting and style survive.

    Any citation not referenced by a placeholder is DELETED — which is the
    RefWorks-correct way to drop a source, since the bibliography is
    regenerated from the surviving tags.
    """
    cits = citation_nodes(p)
    tmpl = _template_run(p)
    if tmpl is None and cits:
        tmpl = copy.deepcopy(cits[0].find(qn("w:sdtContent")).find(qn("w:r")))
    kept = set()

    for c in para_children(p):
        p._p.remove(c)

    def add_run(text):
        if text == "":
            return
        r = copy.deepcopy(tmpl) if tmpl is not None else p._p.makeelement(qn("w:r"), {})
        for t in list(r.findall(qn("w:t"))):
            r.remove(t)
        for br in list(r.findall(qn("w:br"))):
            r.remove(br)
        t = r.makeelement(qn("w:t"), {})
        t.text = text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.append(t)
        p._p.append(r)

    for chunk in re.split(r"(\{C\d+\})", new_text):
        m = re.fullmatch(r"\{C(\d+)\}", chunk)
        if m:
            i = int(m.group(1)) - 1
            if i < 0 or i >= len(cits):
                raise IndexError(
                    f"set_text: placeholder {chunk} but this paragraph has "
                    f"{len(cits)} citation(s). Never invent a citation index.")
            p._p.append(cits[i])
            kept.add(i)
        else:
            add_run(chunk)
    return [i + 1 for i in range(len(cits)) if i not in kept]   # dropped indices

def find_para(doc_blocks, needle, occurrence=0):
    hits = [b for b in doc_blocks
            if isinstance(b, Paragraph) and needle in annotate(b)]
    if not hits:
        raise LookupError(f"find_para: no paragraph contains {needle!r}")
    return hits[occurrence]

def insert_after(p, text, style=None):
    """Insert a new paragraph immediately after p, cloning its formatting."""
    new = copy.deepcopy(p._p)
    for c in list(new.iterchildren()):
        if c.tag in (qn("w:r"), qn("w:sdt"), qn("w:hyperlink")):
            new.remove(c)
    p._p.addnext(new)
    np = Paragraph(new, p._parent)
    if style:
        np.style = style
    set_text(np, text)
    return np

def delete_para(p):
    p._p.getparent().remove(p._p)


# ──────────────────────────────────────────────────────────────────────
# Region rebuilding with a citation pool
# ──────────────────────────────────────────────────────────────────────
# Restructuring a section moves prose between paragraphs, but a RefWorks
# citation control lives inside one <w:p> and cannot be recreated. These
# helpers detach the sdt ELEMENTS into a labelled pool first, then re-attach
# them (the same objects, never copies) wherever the new prose puts them.

def harvest_citations(paras, prefix):
    """Detach every citation in `paras` into {label: sdt_element}."""
    pool = {}
    for i, p in enumerate(paras):
        for j, sdt in enumerate(citation_nodes(p), 1):
            label = f"{prefix}{i}_{j}"
            p._p.remove(sdt)
            pool[label] = sdt
    return pool


def style_like(p, bold=False, italic=False):
    for r in p.runs:
        r.bold = bold or None
        r.italic = italic or None
    return p


def build_region(after_para, blocks, pool, body_template):
    """Insert `blocks` after `after_para`, drawing citations from `pool`.

    Each block is (kind, text) where kind is "h1" (bold), "h2" (bold italic),
    "p" (body) or "blank". Text may carry {LABEL} placeholders naming pooled
    citations; each is re-inserted as the original element, so a citation may
    move to any paragraph but can be used only once.
    """
    used = set()
    cur = after_para
    for kind, text in blocks:
        cur = insert_after(cur, "")
        if kind == "blank":
            continue
        segs = re.split(r"(\{[A-Za-z]\d+_\d+\})", text)
        tmpl = _template_run(body_template)
        for seg in segs:
            m = re.fullmatch(r"\{([A-Za-z]\d+_\d+)\}", seg)
            if m:
                label = m.group(1)
                if label not in pool:
                    raise KeyError(f"build_region: unknown citation label {label}")
                if label in used:
                    raise ValueError(f"build_region: citation {label} used twice")
                used.add(label)
                cur._p.append(pool[label])
            elif seg:
                r = copy.deepcopy(tmpl) if tmpl is not None else cur._p.makeelement(qn("w:r"), {})
                for t in list(r.findall(qn("w:t"))): r.remove(t)
                for br in list(r.findall(qn("w:br"))): r.remove(br)
                t = r.makeelement(qn("w:t"), {}); t.text = seg
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                r.append(t)
                cur._p.append(r)
        style_like(cur, bold=(kind in ("h1", "h2")), italic=(kind == "h2"))
    return cur, used


def set_caption(p, text):
    """Caption text with only the first sentence bold, per house style."""
    m = re.match(r"^(.*?[.!?])(\s+)(.*)$", text, re.S)
    if not m:
        set_text(p, text)
        for r in p.runs: r.bold = True
        return p
    head, gap, rest = m.group(1), m.group(2), m.group(3)
    set_text(p, head + gap + rest)
    # rebuild so the split lands on a run boundary
    tmpl = _template_run(p)
    for c in para_children(p):
        p._p.remove(c)
    for chunk, bold in ((head + gap, True), (rest, False)):
        r = copy.deepcopy(tmpl) if tmpl is not None else p._p.makeelement(qn("w:r"), {})
        for t in list(r.findall(qn("w:t"))): r.remove(t)
        t = r.makeelement(qn("w:t"), {}); t.text = chunk
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.append(t)
        p._p.append(r)
    for r in p.runs:
        r.bold = None
    p.runs[0].bold = True
    return p
