# Copyright (c) 2026 Tiago Pinto <tiago@donttrustverify.pt>
# SPDX-License-Identifier: MIT
"""test_reorg.py: exercise NodeHeaderSource against a SIMULATED node that
reorganises between the header read and the depth read.

Usage: python3 test_reorg.py <artifact> <proof.ots>

Requires on PYTHONPATH: the EMILIA verifier's src/ directory (commit
6ea9afb) and the directory holding node_header_source.py.

No real node is contacted. The simulated node serves synthetic 80-byte
headers that carry the real Merkle roots and nTime values of blocks
968588 and 968635, so the verifier's replay of the real proof matches
them. The headers carry no proof of work and their hashes are not the
real block hashes. Nothing printed here is a statement about the Bitcoin
chain; it is a statement about how the adapter behaves when the chain it
is reading changes.

Scenarios:

  S0  no reorganisation                      expected: valid at 968588
  S1  the block at 968588 is replaced after   expected: unverifiable
      its header is read and before its
      depth is read
  S2  the block at 968588 is replaced during  expected: unverifiable
      the depth read, after the depth value
      is obtained and before the re-check
"""

import hashlib
import sys

from scitt_time_anchor import ProofBundle, verify_anchor

from node_header_source import NodeHeaderSource


ROOTS = {  # internal byte order, as replay produces them
    968588: '08bd49c1a509c1a3fe7a1132f8db6840426904d0817ad9e7e8c0375081df31db',
    968635: '07df4622672a7a205a4d834d5040e7d26023d0c6ba6d42c370d431c2b6b36fb5',
}
NTIME = {968588: 1790370293, 968635: 1790395667}
TIP = 968741


def synthetic_header(height, variant):
    raw = ((4).to_bytes(4, 'little') + bytes(32) + bytes.fromhex(ROOTS[height])
           + NTIME[height].to_bytes(4, 'little') + bytes(4)
           + variant.to_bytes(4, 'little'))
    block_hash = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()
    return raw, block_hash


class SimulatedNode:
    """Answers getblockhash and getblockheader like bitcoind, from memory.

    A block replaced by reorg() stays retrievable by hash with
    confirmations -1, as bitcoind reports for blocks off the active chain.
    """

    def __init__(self):
        self.active = {h: synthetic_header(h, 0) for h in ROOTS}
        self.stale = {}
        self._after_verbose_read = None

    def reorg(self, height):
        raw, old_hash = self.active[height]
        self.stale[old_hash] = (height, raw)
        self.active[height] = synthetic_header(height, 1)

    def reorg_after_next_verbose_read(self, height):
        self._after_verbose_read = height

    def call(self, method, *params):
        if method == 'getblockhash':
            return self.active[params[0]][1]
        if method == 'getblockheader':
            block_hash, verbose = params
            result = None
            for height, (raw, h) in self.active.items():
                if h == block_hash:
                    result = {'height': height, 'confirmations': TIP - height + 1} if verbose else raw.hex()
            if result is None and block_hash in self.stale:
                height, raw = self.stale[block_hash]
                result = {'height': height, 'confirmations': -1} if verbose else raw.hex()
            if result is None:
                raise KeyError('unknown block')
            if verbose and self._after_verbose_read is not None:
                pending, self._after_verbose_read = self._after_verbose_read, None
                self.reorg(pending)
            return result
        raise KeyError(method)


class ReorgBeforeDepth(NodeHeaderSource):
    """S1: replace the block just before the adapter reads its depth."""

    def confirmations_on(self, height):
        self.rpc.reorg(height)
        return super().confirmations_on(height)


class ReorgDuringDepth(NodeHeaderSource):
    """S2: replace the block right after the depth value is obtained."""

    def confirmations_on(self, height):
        self.rpc.reorg_after_next_verbose_read(height)
        return super().confirmations_on(height)


def run(label, source, artifact, bundle, expected_outcome, expected_height):
    report = verify_anchor(artifact, bundle, source)
    ok = (report.outcome.value == expected_outcome
          and report.block_height == expected_height)
    print(f'=== {label}')
    print(f'outcome:        {report.outcome.value}')
    print(f'reason:         {report.reason}')
    print(f'block_height:   {report.block_height}')
    print(f'confirmations:  {report.confirmations}')
    for b in report.branches:
        print(f'branch:         height={b.height} state={b.state} ops={b.operation_count}')
    for method, height, outcome in source.log:
        print(f'adapter:        {method}({height}) -> {outcome}')
    print(f'expected:       {expected_outcome} at {expected_height}')
    print(f'check:          {"PASS" if ok else "FAIL"}')
    print()
    return ok


def main():
    artifact = open(sys.argv[1], 'rb').read()
    proof = open(sys.argv[2], 'rb').read()
    digest = hashlib.sha256(artifact).hexdigest()
    bundle = ProofBundle(ots_proof=proof, claimed_hash='sha256:' + digest)

    print('SIMULATED NODE. No real chain is contacted; see the module docstring.')
    print(f'artifact sha256 {digest}')
    print(f'proof    sha256 {hashlib.sha256(proof).hexdigest()}')
    print()

    results = [
        run('S0 no reorganisation', NodeHeaderSource(SimulatedNode()),
            artifact, bundle, 'valid', 968588),
        run('S1 block replaced between header read and depth read',
            ReorgBeforeDepth(SimulatedNode()), artifact, bundle, 'unverifiable', 968588),
        run('S2 block replaced during depth read',
            ReorgDuringDepth(SimulatedNode()), artifact, bundle, 'unverifiable', 968588),
    ]
    print(f'summary: {sum(results)}/{len(results)} PASS')
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
