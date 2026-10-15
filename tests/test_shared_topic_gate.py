"""The one gate for every catch action that can let the shared legacy discovery topic go empty (D-02 to D-05, D-13)."""

import pytest

from custom_components.mqtt_actions.discovery import DiscoveryContent
from custom_components.mqtt_actions.takeover import PeerKeep, TopicVerdict, shared_topic_verdict

# What the online peers announce about device X, as the situations of the research table, and the peer state each
# one reads as: a peer that lists X keeps it, one that lists other ids is silent on X, an older version sends no list,
# an instance announced online but not heard yet has no row, and an offline peer never counts
PEER_SITUATIONS = {
    "lists_x": PeerKeep.KEPT,
    "silent_on_x": PeerKeep.CLEAR,
    "older_version": PeerKeep.UNKNOWN,
    "online_not_heard": PeerKeep.UNHEARD,
    "offline": PeerKeep.CLEAR,
}


def _expected(*, owner: bool, content: DiscoveryContent, local_keeps: bool, peers: PeerKeep) -> TopicVerdict:
    """
    Return the verdict of the research table (Q6), as group rules.

    EXPORT and UNKNOWN content give nothing; EMPTY gives only the removal; LEGACY gives nothing for a follower or with a
    local keep; for an owner without a local keep it gives the removal and the clear for CLEAR, only the re-arm for
    UNHEARD and nothing for KEPT and UNKNOWN.
    """
    nothing = TopicVerdict(remove_disabled=False, may_clear=False, rearm=False)
    if content in {DiscoveryContent.EXPORT, DiscoveryContent.UNKNOWN}:
        return nothing
    if content is DiscoveryContent.EMPTY:
        return TopicVerdict(remove_disabled=True, may_clear=False, rearm=False)
    if not owner or local_keeps:
        return nothing
    if peers is PeerKeep.CLEAR:
        return TopicVerdict(remove_disabled=True, may_clear=True, rearm=False)
    if peers is PeerKeep.UNHEARD:
        return TopicVerdict(remove_disabled=False, may_clear=False, rearm=True)
    return nothing


@pytest.mark.parametrize("local_keeps", [False, True], ids=["no_local_keep", "local_keep"])
@pytest.mark.parametrize("content", list(DiscoveryContent), ids=[content.name for content in DiscoveryContent])
@pytest.mark.parametrize("situation", list(PEER_SITUATIONS))
@pytest.mark.parametrize("owner", [True, False], ids=["owner", "follower"])
def test_the_shared_topic_verdict_follows_the_table(
    owner: bool,
    situation: str,
    content: DiscoveryContent,
    local_keeps: bool,
) -> None:
    """D-13: role x peer situation x content x local keep, for the twin removal, the explicit clear and the re-arm."""
    peers = PEER_SITUATIONS[situation]

    verdict = shared_topic_verdict(owner=owner, content=content, local_keeps=local_keeps, peers=peers)

    assert verdict == _expected(owner=owner, content=content, local_keeps=local_keeps, peers=peers)


def test_a_follower_never_lets_the_topic_go_empty_on_legacy_content() -> None:
    """D-05: whatever the peers announce and whatever it keeps, a follower lets no LEGACY topic go empty."""
    for peers in PeerKeep:
        for local_keeps in (False, True):
            verdict = shared_topic_verdict(
                owner=False, content=DiscoveryContent.LEGACY, local_keeps=local_keeps, peers=peers
            )
            assert verdict.remove_disabled is False
            assert verdict.may_clear is False


def test_the_peer_states_are_the_four_strings() -> None:
    assert [state.value for state in PeerKeep] == ["clear", "unheard", "unknown", "kept"]
