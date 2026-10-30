#!/usr/bin/env python3.13
"""Track B (Index) solution for Speed Demon 2026.

Same semantics as the naive reference: ASCII tokens (lowercased [a-z0-9]+),
boolean operators applied left to right, exact phrase matching inside a
single document, and output "count sum id1 ... id10". Standard library only.

Build: one pass over docs.txt.
  * Each term gets a sorted postings array('I') of document ids.
  * Each document's token stream is kept as term ids in one flat byte buffer,
    so phrase queries are verified with bytes.find() and never re-tokenize.
Query: postings are combined with array-based AND / OR / NOT. Identical query
lines are answered once.
"""
from __future__ import annotations

import os
import re
import sys
from array import array
from bisect import bisect_left

DOCS_FILE = "docs.txt"
QUERIES_FILE = "queries.txt"
RESULTS_FILE = "results.txt"

TOKEN_RE = re.compile(rb"[a-z0-9]+")
EMPTY = array("I")

# If one AND operand is at least this many times longer than the other,
# galloping (binary search) beats a linear scan.
GALLOP_RATIO = 32


class Index:
    def __init__(self) -> None:
        self.vocab: dict[bytes, int] = {}
        self.postings: list[array] = []
        # Token ids of every document, 4 bytes each (native 'I' order).
        self.stream: bytes = b""
        # Document d owns token units offsets[d] .. offsets[d + 1] - 1.
        self.offsets: array = array("Q", [0])

    def postings_for(self, term: bytes) -> array:
        tid = self.vocab.get(term)
        return self.postings[tid] if tid is not None else EMPTY


def build_index(path: str) -> Index:
    idx = Index()
    vocab = idx.vocab
    postings = idx.postings
    offsets = idx.offsets
    stream = array("I")
    doc_count = 0

    with open(path, "rb") as f:
        for line in f:
            if line.endswith(b"\n"):
                line = line[:-1]
            id_field, _, text = line.partition(b"\t")
            doc_id = int(id_field)
            if doc_id != doc_count:
                raise ValueError(f"document ids must be 0..N-1 in order, got {doc_id}")
            doc_count += 1

            ids = []
            append = ids.append
            for tok in TOKEN_RE.findall(text.lower()):
                tid = vocab.get(tok)
                if tid is None:
                    tid = len(postings)
                    vocab[tok] = tid
                    postings.append(array("I"))
                append(tid)

            stream.extend(ids)
            offsets.append(len(stream))
            # Documents arrive in id order, so each postings list stays sorted
            # and gets at most one entry per document.
            for tid in set(ids):
                postings[tid].append(doc_id)

    idx.stream = stream.tobytes()
    return idx


# ---- set operations on sorted, duplicate-free postings arrays -------------

def _and(a: array, b: array) -> array:
    if len(a) > len(b):
        a, b = b, a
    if not a:
        return EMPTY
    if len(b) >= len(a) * GALLOP_RATIO:
        out = array("I")
        lo = 0
        nb = len(b)
        for x in a:
            lo = bisect_left(b, x, lo)
            if lo == nb:
                break
            if b[lo] == x:
                out.append(x)
        return out
    small = set(a)
    return array("I", [x for x in b if x in small])


def _or(a: array, b: array) -> array:
    if not a:
        return array("I", b)
    if not b:
        return array("I", a)
    merged = set(a)
    merged.update(b)
    return array("I", sorted(merged))


def _not(a: array, b: array) -> array:
    if not a or not b:
        return array("I", a)
    removed = set(b)
    return array("I", [x for x in a if x not in removed])


# ---- query evaluation -----------------------------------------------------

def run_bool(idx: Index, words: list[bytes]) -> array:
    result = idx.postings_for(words[0])
    for op, term in zip(words[1::2], words[2::2]):
        p = idx.postings_for(term)
        if op == b"AND":
            result = _and(result, p)
        elif op == b"OR":
            result = _or(result, p)
        elif op == b"NOT":
            result = _not(result, p)
        else:
            raise ValueError(f"unknown operator {op!r}")
    return result


def _contains_aligned(buf: bytes, pat: bytes, lo: int, hi: int) -> bool:
    """True if pat occurs in buf[lo:hi] starting on a 4-byte token boundary.
    lo is always a multiple of 4, so the alignment test is relative to lo."""
    pos = buf.find(pat, lo, hi)
    while pos != -1:
        if (pos - lo) & 3 == 0:
            return True
        pos = buf.find(pat, pos + 1, hi)
    return False


def run_phrase(idx: Index, terms: list[bytes]) -> array:
    ids = []
    for t in terms:
        tid = idx.vocab.get(t)
        if tid is None:
            return EMPTY
        ids.append(tid)

    candidates = idx.postings[ids[0]]
    for tid in set(ids[1:]):
        candidates = _and(candidates, idx.postings[tid])
    if not candidates:
        return EMPTY

    pat = array("I", ids).tobytes()
    buf = idx.stream
    offs = idx.offsets
    out = array("I")
    for d in candidates:
        lo = offs[d] * 4
        hi = offs[d + 1] * 4
        if _contains_aligned(buf, pat, lo, hi):
            out.append(d)
    return out


def format_result(doc_ids: array) -> str:
    """count, sum of ids, then up to 10 smallest ids ascending."""
    head = [len(doc_ids), sum(doc_ids)]
    head.extend(doc_ids[:10])
    return " ".join(str(x) for x in head)


def answer(idx: Index, line: bytes) -> str:
    kind, _, rest = line.partition(b" ")
    if kind == b"BOOL":
        return format_result(run_bool(idx, rest.split(b" ")))
    if kind == b"PHRASE":
        if not (rest.startswith(b'"') and rest.endswith(b'"')):
            raise ValueError(f"bad phrase query {line!r}")
        return format_result(run_phrase(idx, rest[1:-1].split(b" ")))
    raise ValueError(f"bad query {line!r}")


def main(data_dir: str, out_dir: str) -> None:
    idx = build_index(os.path.join(data_dir, DOCS_FILE))

    cache: dict[bytes, str] = {}
    results = []
    with open(os.path.join(data_dir, QUERIES_FILE), "rb") as f:
        for line in f:
            if line.endswith(b"\n"):
                line = line[:-1]
            r = cache.get(line)
            if r is None:
                r = answer(idx, line)
                cache[line] = r
            results.append(r)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, RESULTS_FILE), "w", encoding="ascii", newline="\n") as f:
        f.write("".join(r + "\n" for r in results))


if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "/data"
    out = sys.argv[2] if len(sys.argv) > 2 else "/out"
    main(data, out)
    sys.exit(0)
