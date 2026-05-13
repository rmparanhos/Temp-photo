from __future__ import annotations

from pathlib import Path

# lr:pickStatus -1 = Rejected, 0 = Unflagged, 1 = Picked
_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="ella">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:lr="http://ns.adobe.com/lightroom/1.0/">
   <xmp:Rating>0</xmp:Rating>
   <lr:pickStatus>-1</lr:pickStatus>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""


def write_rejected(photo_path: Path) -> Path:
    """Write an XMP sidecar marking photo_path as rejected in Lightroom Classic."""
    xmp_path = photo_path.with_suffix(".xmp")
    xmp_path.write_text(_TEMPLATE, encoding="utf-8")
    return xmp_path
