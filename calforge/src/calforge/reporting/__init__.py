"""Report generation and data exports.

``documents`` builds self-contained HTML (pure Python, no Qt — fully testable)
using a deliberately conservative subset (tables, headings, inline styles) so
the same markup renders correctly both in a browser and through Qt's rich-text
engine when exported to PDF (see ``reporting.pdf``). ``exports`` serialises
data to CSV/JSON.
"""
