"""
v7.3: address explorer. v7.16: the explorer screens are gone from the interface; the
derivation it used (address.SinglesigExplorer, DescriptorExplorer) is part of the core and
still checked against embit here.
"""
import pytest

from nonceverify import address as A

pytest.importorskip("embit")
from embit import script                                                          # noqa: E402
from embit.descriptor import Descriptor as EDescriptor                            # noqa: E402
from test_nonceverify_address import eaddr, eroot, master, multisig_descriptor    # noqa: E402


@pytest.mark.parametrize("purpose,maker", [(84, script.p2wpkh), (49, lambda p: script.p2sh(script.p2wpkh(p))),
                                           (44, script.p2pkh)])
def test_singlesig_explorer_matches_embit(purpose, maker):
    root, m = eroot(), master()
    for account in (0, 2):
        e = A.SinglesigExplorer(m, purpose, account)
        for change in (False, True):
            for index in (0, 1, 57):
                text, path = e.address(change, index)
                want = eaddr(maker(root.derive(f"m/{purpose}h/0h/{account}h/{int(change)}/{index}").key.get_public_key()))
                assert text == want and path[-2:] == [int(change), index]


def test_descriptor_explorer_matches_embit():
    text, _ = multisig_descriptor()
    e = A.DescriptorExplorer(A.parse_descriptor(text))
    ed = EDescriptor.from_string(text.split("#")[0])
    for change in (False, True):
        for index in (0, 9):
            assert e.address(change, index)[0] == eaddr(ed.derive(index, branch_index=int(change)).script_pubkey())
