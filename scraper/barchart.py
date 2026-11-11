"""Parse eBird 'Download Histogram Data' (bar chart) TSV files.

eBird splits each month into 4 'weeks': days 1-7, 8-14, 15-21, 22-end -> 48 columns.
Format (roughly):

    Frequency of observations in the selected location(s).:
    Number of taxa: 312

    \tJan\t\t\t\tFeb ...
    Sample Size:\t12.0\t30.0\t...
    Common Ostrich (<em class="sci">Struthio camelus</em>)\t0.0\t...
"""

import datetime as dt
import re
from dataclasses import dataclass

NAME_RE = re.compile(r"^(?P<common>.+?)\s*\((?:<em[^>]*>)?(?P<sci>[^<)]+)(?:</em>)?\)\s*$")


def week_index(d: dt.date) -> int:
    """0..47 bar-chart column for a date."""
    return (d.month - 1) * 4 + min((d.day - 1) // 7, 3)


def week_window(d: dt.date, window: int) -> list[int]:
    i = week_index(d)
    return [(i + k) % 48 for k in range(-window, window + 1)]


@dataclass
class BarchartRow:
    common_name: str
    scientific_name: str
    values: list[float]  # 48 weekly frequencies


@dataclass
class Barchart:
    sample_sizes: list[float]
    rows: list[BarchartRow]

    def window_stats(self, weeks: list[int]) -> tuple[int, dict[str, float]]:
        """Sample-size-weighted frequency over the given weeks, keyed by scientific name."""
        n = sum(self.sample_sizes[w] for w in weeks)
        out = {}
        for row in self.rows:
            if n > 0:
                f = sum(row.values[w] * self.sample_sizes[w] for w in weeks) / n
            else:
                f = sum(row.values[w] for w in weeks) / len(weeks)
            out[row.scientific_name] = f
        return int(n), out


def _floats(cells: list[str]) -> list[float] | None:
    vals = [c.strip() for c in cells if c.strip() != ""]
    try:
        nums = [float(v) for v in vals]
    except ValueError:
        return None
    return nums if len(nums) == 48 else None


def parse_barchart(text: str) -> Barchart:
    sample_sizes: list[float] | None = None
    rows: list[BarchartRow] = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        label, *cells = line.split("\t")
        label = label.strip()
        nums = _floats(cells)
        if nums is None:
            continue
        if label.lower().startswith("sample size"):
            sample_sizes = nums
            continue
        m = NAME_RE.match(label)
        if not m:
            continue
        rows.append(BarchartRow(m["common"].strip(), m["sci"].strip(), nums))
    if sample_sizes is None:
        raise ValueError("Could not find 'Sample Size' row - is this an eBird histogram TSV?")
    return Barchart(sample_sizes, rows)
