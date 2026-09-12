from bot.agent.response_policy import infer_response_policy


def test_casual_messages_are_short_and_not_forced_into_explanations():
    policy = infer_response_policy("hii")
    assert policy.mode == "casual"
    assert policy.length == "short"
    assert not policy.should_explain


def test_technical_messages_get_adaptive_detailed_policy():
    policy = infer_response_policy("RAG architecture kaise implement karun?")
    assert policy.mode == "technical"
    assert policy.length == "detailed"
    assert policy.should_explain


def test_profile_style_is_respected_for_general_conversation():
    policy = infer_response_policy("aaj kaafi interesting din tha", {"language": "hindi", "reply_style": "medium"})
    assert policy.language == "hindi"
    assert policy.length == "medium"
