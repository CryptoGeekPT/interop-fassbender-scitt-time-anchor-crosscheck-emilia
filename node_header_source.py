# Copyright (c) 2026 Tiago Pinto <tiago@donttrustverify.pt>
# SPDX-License-Identifier: MIT
"""node_header_source.py: a ValidatedHeaderSource backed by the operator's
own Bitcoin full node.

Adapter between the independent verifier for
draft-fassbender-scitt-time-anchor-06 published by EMILIA Protocol
(github.com/emiliaprotocol/scitt-time-anchor-verifier, commit
6ea9afb257df9c9de28fc04001e9cc70124aa6fd, interface
scitt_time_anchor.model.ValidatedHeaderSource) and a self-operated Bitcoin
full node reached over JSON-RPC.

It contains no verification logic. Replay, branch classification, height
selection and the confirmation gate are all performed by the verifier.
This file only answers the two questions the interface asks, and answers
None whenever it cannot answer them from the node's active chain.

Guarantees:

1. header_by_height(H) returns a header only if the node reports the
   block at H on its active chain (getblockheader verbose 'confirmations'
   >= 1 and 'height' == H), and the 80 returned bytes hash (double
   SHA-256, reversed) to the block hash the node gave for H.

2. confirmations_on(H) answers only for a height whose header this object
   returned, and only if the node's active chain carries that same block
   at H both before and after the depth is read. Otherwise it returns
   None, which the verifier treats as unverifiable. A reorganisation
   between the header read and the depth read therefore yields
   unverifiable, never a depth taken from a different chain than the
   header.

Why the node qualifies: -06 Section 3.1, note on header sources, requires
that the verifier can place the header on the validated most-work chain,
and states that validating the chain establishes that. The node is the
operator's own full node, not the anchoring service; its active chain is
the most-work chain it has itself validated.

The RPC client is BitcoinRPC from node_rpc.py in the operator's frozen
-03 package (SHA256SUMS 9c55d358..., anchored at block 960468). Only its
call() method is used.
"""

import hashlib

from scitt_time_anchor import BlockHeader


class NodeHeaderSource:
    """ValidatedHeaderSource over the operator's own full node."""

    def __init__(self, rpc):
        self.rpc = rpc
        self._returned = {}   # height -> block hash (display hex) we returned
        self.log = []         # (method, height, outcome) for the run record

    def _active_hash(self, height):
        return self.rpc.call('getblockhash', height)

    def header_by_height(self, height):
        try:
            block_hash = self._active_hash(height)
            raw = bytes.fromhex(self.rpc.call('getblockheader', block_hash, False))
            info = self.rpc.call('getblockheader', block_hash, True)
        except Exception as e:
            self.log.append(('header_by_height', height, f'None: rpc error {e}'))
            return None
        if len(raw) != 80:
            self.log.append(('header_by_height', height, 'None: not 80 bytes'))
            return None
        if hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex() != block_hash:
            self.log.append(('header_by_height', height, 'None: bytes do not hash to block hash'))
            return None
        if info.get('height') != height or info.get('confirmations', -1) < 1:
            self.log.append(('header_by_height', height, 'None: not on active chain at this height'))
            return None
        self._returned[height] = block_hash
        self.log.append(('header_by_height', height, f'header {block_hash}'))
        return BlockHeader(raw)

    def confirmations_on(self, height):
        block_hash = self._returned.get(height)
        if block_hash is None:
            self.log.append(('confirmations_on', height, 'None: no header returned for this height'))
            return None
        try:
            before = self._active_hash(height)
            info = self.rpc.call('getblockheader', block_hash, True)
            after = self._active_hash(height)
        except Exception as e:
            self.log.append(('confirmations_on', height, f'None: rpc error {e}'))
            return None
        if before != block_hash or after != block_hash:
            self.log.append(('confirmations_on', height, 'None: active chain changed at this height'))
            return None
        depth = info.get('confirmations', -1)
        if not isinstance(depth, int) or depth < 1:
            self.log.append(('confirmations_on', height, 'None: block left the active chain'))
            return None
        self.log.append(('confirmations_on', height, f'{depth}'))
        return depth


class NullHeaderSource:
    """No validated chain source: every question is answered with None."""

    def __init__(self):
        self.log = []

    def header_by_height(self, height):
        self.log.append(('header_by_height', height, 'None: no validated chain source'))
        return None

    def confirmations_on(self, height):
        self.log.append(('confirmations_on', height, 'None: no validated chain source'))
        return None
