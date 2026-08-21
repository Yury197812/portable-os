"""Test pp_html_specific standalone preprocessor + brotli compression on synthetic HTML."""
import re
import time
import zlib
from pathlib import Path

SAMPLE = b"""<!DOCTYPE html>
<!-- This is a comment with lots of whitespace.   -->
<HTML lang="en">
  <HEAD>
    <META charset="utf-8">
    <META name="viewport" content="width=device-width, initial-scale=1">
    <TITLE>Test page</TITLE>
    <!-- Another comment, also whitespacey. -->
  </HEAD>
  <body class="main  another-class   third-class">
    <DIV id="container" class="wrapper">
      <P class="text  highlight">Hello   world,    this is    a test.</P>
      <A href="https://example.com" class="link  external" target="_blank">Link</A>
      <DIV class="nested">
        <span style="color: red;">Red text</span>
        <span class="class-a  class-b  class-c">Three classes</span>
      </DIV>
      <P>Some content   with   extra   spaces.</P>
    </DIV>
  </body>
</HTML>
"""


def pp_html_specific(data: bytes) -> bytes:
    """Standalone HTML preprocessor (no envelope). Lossless on semantics."""
    txt = data.decode("utf-8", errors="replace")
    # 1. Remove HTML comments
    txt = re.sub(r"<!--.*?-->", "", txt, flags=re.DOTALL)
    # 2. Collapse whitespace between tags
    txt = re.sub(r">\s+<", "><", txt)
    # 3. Lowercase tags (but not attribute values or text)
    txt = re.sub(r"<(/?)([A-Za-z][A-Za-z0-9]*)", lambda m: f"<{m.group(1)}{m.group(2).lower()}", txt)
    # 4. Sort attributes within tags (alphabetical)
    def sort_attrs(m):
        tag = m.group(1)
        body = m.group(2)
        # Parse attributes: key="value" key='value' key=value
        attrs = re.findall(r'(\S+?)="([^"]*)"|(\S+?)=\'([^\']*)\'|(\S+?)=(\S+)', body)
        attr_pairs = []
        for a, av, b, bv, c, cv in attrs:
            if a: attr_pairs.append((a, av))
            elif b: attr_pairs.append((b, bv))
            else: attr_pairs.append((c, cv))
        attr_pairs.sort()
        new = " ".join(f'{k}="{v}"' for k, v in attr_pairs)
        return f"<{tag} {new}>" if new else f"<{tag}>"
    txt = re.sub(r"<(\w+)([^>]*?)>", sort_attrs, txt)
    # 5. Remove redundant meta charset (default UTF-8)
    txt = re.sub(r'<meta\s+charset=["\']?utf-?8["\']?\s*/?>', "", txt, flags=re.IGNORECASE)
    return txt.encode("utf-8")


def main():
    raw = SAMPLE
    pp = pp_html_specific(raw)
    print(f"raw size:   {len(raw):>5d} bytes")
    print(f"pp size:     {len(pp):>5d} bytes (raw - {100*(1-len(pp)/len(raw)):.1f}% saved before compression)")
    # Compress both with brotli (offline benchmark — gzip is what we have)
    for level in [6, 9]:
        cmp_raw = zlib.compress(raw, level)
        cmp_pp = zlib.compress(pp, level)
        print(f"zlib -{level} raw: {len(cmp_raw):>5d} bytes ({100*len(cmp_raw)/len(raw):.2f}%)")
        print(f"zlib -{level} pp:  {len(cmp_pp):>5d} bytes ({100*len(cmp_pp)/len(raw):.2f}%)")
    # Roundtrip-safety check
    raw2 = pp
    raw2 = pp_html_specific(pp); pp2 = pp_html_specific(raw2)
    print(f"\nidempotent (pp(pp(x)) == pp(x)): {pp == pp2}")
    print(f"raw bytes after pp (lowercase tags visible):")
    print(pp.decode("utf-8"))


if __name__ == "__main__":
    main()
