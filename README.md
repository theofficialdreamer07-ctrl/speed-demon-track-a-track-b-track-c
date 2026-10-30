# Track B: Index

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/b-index.md).

## Approach

The build is a single streaming pass over `docs.txt`. Each document is lowercased and split into ASCII `[a-z0-9]+` tokens. Every distinct term gets an integer id and a postings list stored as a sorted `array('I')` of document ids. Because documents arrive in id order, the lists stay sorted without any sorting step, and each document is added at most once per term.

Each document's token stream is also kept as term ids in one flat byte buffer, with an offsets array marking where each document starts and ends. Phrase queries first intersect the postings of the phrase's terms to get candidate documents, then search only those documents' slices of the buffer for the id sequence, using `bytes.find` and rejecting matches that do not start on a token boundary. Nothing is re-tokenized at query time.

Boolean queries are evaluated left to right, as in the spec. AND uses a two-pointer style scan with galloping (binary search) when the operands differ greatly in size. OR merges via a set. NOT removes the right operand's ids from the left. Identical query lines are answered once and cached.

Output is the document count, the sum of matching ids, and the ten smallest ids, which fall out of the already-sorted result.

`tests/check_against_reference.py` checks the solution against a brute-force oracle on random corpora and queries, covering uppercase terms, non-ASCII bytes, empty documents, and all three operators.

## Dependencies

None. Standard library only.

## With another 24 hours

- Measure build and query time separately on the live board, then profile which part dominates.
- Replace the Python-level AND/NOT list comprehensions with a compressed bitmap or delta-encoded postings, which would cut both memory and the cost of the large intersections.
- Store postings for frequent terms as bitsets and rare terms as sorted arrays, switching on document frequency.
- Build the postings and token stream in a single C-speed pass, for example with `re.finditer` over the whole file, instead of per-line processing.
- Use `multiprocessing` for the build by splitting docs.txt into chunks with disjoint document id ranges and merging postings.
