# Copyright (c) 2026 Tiago Pinto <tiago@donttrustverify.pt>
# SPDX-License-Identifier: MIT
"""run_emilia.py: run the EMILIA -06 verifier on one artifact and proof,
twice: once with the operator's node as the validated chain source, once
with no chain source.

Usage: python3 run_emilia.py <artifact> <proof.ots>

Requires on PYTHONPATH: the verifier's src/ directory (commit 6ea9afb)
and the operator's frozen -03 package (for node_rpc.BitcoinRPC).
"""

import hashlib
import sys

import scitt_time_anchor
from scitt_time_anchor import ProofBundle, verify_anchor, MIN_CONFIRMATIONS
from node_rpc import BitcoinRPC

from node_header_source import NodeHeaderSource, NullHeaderSource


def show(label, report, source):
    print(f'=== {label}')
    print(f'outcome:        {report.outcome.value}')
    print(f'reason:         {report.reason}')
    print(f'block_height:   {report.block_height}')
    print(f'rwcp (nTime):   {report.reference_wall_clock_projection}')
    print(f'confirmations:  {report.confirmations}')
    for b in report.branches:
        print(f'branch:         height={b.height} state={b.state} ops={b.operation_count}')
    for method, height, outcome in source.log:
        print(f'source:         {method}({height}) -> {outcome}')
    print()


def main():
    artifact_path, proof_path = sys.argv[1], sys.argv[2]
    artifact = open(artifact_path, 'rb').read()
    proof = open(proof_path, 'rb').read()
    digest = hashlib.sha256(artifact).hexdigest()

    print(f'verifier:       scitt_time_anchor {scitt_time_anchor.__version__} '
          f'(draft -06), MIN_CONFIRMATIONS={MIN_CONFIRMATIONS}')
    print(f'artifact:       {artifact_path} sha256 {digest}')
    print(f'proof:          {proof_path} sha256 {hashlib.sha256(proof).hexdigest()}')
    print()

    bundle = ProofBundle(ots_proof=proof, claimed_hash='sha256:' + digest)

    node = NodeHeaderSource(BitcoinRPC())
    show('validated chain source: operator full node', verify_anchor(artifact, bundle, node), node)

    null = NullHeaderSource()
    show('no validated chain source', verify_anchor(artifact, bundle, null), null)


if __name__ == '__main__':
    main()
