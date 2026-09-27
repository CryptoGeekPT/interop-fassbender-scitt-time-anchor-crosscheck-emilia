# interop-fassbender-scitt-time-anchor-crosscheck-emilia

A node-backed header source for the independent verifier of
draft-fassbender-scitt-time-anchor-06 published by EMILIA Protocol, and
the record of one cross-check vector run through it.

## What is here

- `node_header_source.py`: an adapter that implements the verifier's
  `ValidatedHeaderSource` interface over the operator's own Bitcoin full
  node. It contains no verification logic.
- `run_emilia.py`: runs the verifier on one artifact and proof, once with
  the node as chain source and once with no chain source.
- `test_reorg.py`: tests the adapter against a simulated node that
  changes the block at the attested height between the header read and
  the depth read.
- `vector/`: the artifact and its proofs.
- `evidence/`: the outputs of the runs described below.
- `anchors/`: a manifest of the adapter files whose hashes were sent to
  EMILIA Protocol, and its Bitcoin proof.

The verifier itself is not included. It is used unmodified from
https://github.com/emiliaprotocol/scitt-time-anchor-verifier at commit
`6ea9afb257df9c9de28fc04001e9cc70124aa6fd`, which implements -06. Its
own test suite (26 tests) passes on that checkout.

## The vector

`vector/cc1.txt`: 53 bytes, no trailing newline, content
`crosscheck emilia/donttrustverify 2026-09-25 vector 1`, SHA-256
`d2d6506942e9e4784d0d0e67e8da7020aae847db2801985dda50e600f5403c6f`.

It was anchored by an independent producer-side implementation of
draft-fassbender-scitt-time-anchor-03,
https://github.com/CryptoGeekPT/interop-fassbender-scitt-time-anchor-03,
whose manifest (SHA-256 `9c55d358...`) is itself anchored at Bitcoin
block 960468.

- `vector/cc1.txt.ots.pending`: the proof as first written, calendar
  attestations only.
- `vector/cc1.txt.anchored.ots`: the upgraded proof, with three Bitcoin
  branches, two attested at height 968588 and one at 968635.

The first operations of the proof append a 16-byte blinding nonce to the
artifact digest and hash the result (Section 4.3 of -06), so the
calendars received
`ddff22a7068212ae550ed9c1e2aca2aa0233965f6aec54f5d05ebdae9dde9183`,
not the artifact digest.

## Results

All three runs below were performed by the author of this repository, on
his own machine. Runs 1 and 2 used his own full node as the chain
source. The node-backed runs have not been reproduced by EMILIA
Protocol.

| Run | Verifier | Chain source | Outcome | Height | Output |
|-----|----------|--------------|---------|--------|--------|
| 1 | the -03 implementation's verifier, `verify_run.py` from the frozen manifest above | own full node | valid | 968588 | `evidence/verify-2026-09-26.out` |
| 2 | EMILIA -06 verifier at `6ea9afb`, through `node_header_source.py` | own full node | valid | 968588 | `evidence/emilia-run-2026-09-26.out` |
| 3 | EMILIA -06 verifier at `6ea9afb` | none | unverifiable | none | `evidence/emilia-run-2026-09-26.out` |

In run 2 the EMILIA verifier classified all three branches as verified
against the headers the node reported:
`000000000000000000000645853be94e21ff82323d1e4e5deacea3966dc62373` at
968588 and
`00000000000000000000836dfab1879244485960e1ee0a506461ad5a93560ed2` at
968635. It binds to the lowest verified height, 968588.

The normative result is the block height. The nTime of block 968588,
2026-09-25T21:04:53Z, is the informative Reference Wall-Clock
Projection and is shown only alongside it.

The confirmation counts in the outputs (144 in run 1, 154 in run 2)
differ because the runs were made at different chain tips.

EMILIA Protocol's own run of its verifier on this vector is not repeated
here. The joint description of the cross-check will be published
separately.

## Reorganisation handling

The verifier asks the header source two questions at different times:
the header at a height, then the confirmation depth at the selected
height. The adapter ensures both answers come from the same active
chain:

1. `header_by_height(H)` returns a header only if the node reports the
   block at H on its active chain, and the 80 bytes hash to the block
   hash the node gave for H.
2. `confirmations_on(H)` answers only for a height whose header the
   adapter returned, and only if the node's active chain carries that
   same block at H both before and after the depth is read. Otherwise it
   returns `None`, which the verifier reports as unverifiable.

`evidence/test-reorg-2026-09-27.out` records `test_reorg.py` against a
simulated node:

| Scenario | Expected | Result |
|----------|----------|--------|
| S0 no reorganisation | valid at 968588 | PASS |
| S1 block replaced between the header read and the depth read | unverifiable | PASS |
| S2 block replaced after the depth value is read, before the re-check | unverifiable | PASS |

`evidence/test-reorg-mutant-2026-09-27.out` records the same test against
a copy of the adapter with the re-check after the depth read removed. S2
then returns valid and fails (2/3 PASS). The re-check is therefore
necessary: the check before the depth read alone does not catch a change
that happens during it.

The simulated node serves synthetic headers that carry the real Merkle
roots and nTime values of the two blocks. They carry no proof of work
and their hashes are not the real block hashes. The test says nothing
about the Bitcoin chain, only about how the adapter behaves when the
chain it reads changes. In run 2 the adapter found the same block at
968588 before and after reading its depth, so the reorganisation path
was not exercised on the real chain.

## Reproducing

Requires Python 3.11 or later. The node-backed run also requires your
own Bitcoin full node, with RPC credentials in `~/.bitcoin/bitcoin.conf`
(`rpcconnect`, `rpcport`, `rpcuser`, `rpcpassword`).

```sh
git clone https://github.com/emiliaprotocol/scitt-time-anchor-verifier.git emilia-verifier
git -C emilia-verifier checkout 6ea9afb257df9c9de28fc04001e9cc70124aa6fd
git clone https://github.com/CryptoGeekPT/interop-fassbender-scitt-time-anchor-03.git producer-03
git clone https://github.com/CryptoGeekPT/interop-fassbender-scitt-time-anchor-crosscheck-emilia.git crosscheck
cd crosscheck
sha256sum -c SHA256SUMS

# reorganisation test, no node needed
PYTHONPATH=../emilia-verifier/src:. python3 test_reorg.py vector/cc1.txt vector/cc1.txt.anchored.ots

# the mutant check
mkdir -p /tmp/mutant
sed 's/if before != block_hash or after != block_hash:/if before != block_hash:/' node_header_source.py > /tmp/mutant/node_header_source.py
cp test_reorg.py /tmp/mutant/
PYTHONPATH=../emilia-verifier/src python3 /tmp/mutant/test_reorg.py vector/cc1.txt vector/cc1.txt.anchored.ots

# node-backed run and no-source run
PYTHONPATH=../emilia-verifier/src:.:../producer-03 python3 run_emilia.py vector/cc1.txt vector/cc1.txt.anchored.ots
```

The mutant check copies the test next to the altered adapter because
Python imports modules from the script's own directory first.

## Anchors

`anchors/SHA256SUMS-adapter` lists the SHA-256 of the adapter, the runner
and the run 2 output, the same values sent to EMILIA Protocol by email on
2026-09-26.
`anchors/SHA256SUMS-adapter.anchored.ots` attests that manifest at
Bitcoin block 968752. The paths inside the manifest are those of the
author's working directory, so compare the values rather than running
`sha256sum -c` on it.

## Language

`evidence/verify-2026-09-26.out` is output of the -03 implementation,
which prints some labels in Portuguese, the author's working language:
`resultado` is result, `normativo` is normative, `informativa` is
informative, `confirmações` is confirmations.

## Licence

MIT, for the files in this repository. See `LICENSE`. The EMILIA
verifier is licensed separately by its authors.

Tiago Pinto, https://donttrustverify.pt
