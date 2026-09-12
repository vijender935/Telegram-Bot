from bot.domain.learning import empty_profile, merge_profiles, should_extract


def test_preference_learning_detects_natural_language_preferences():
    assert should_extract("Mujhe technical answers examples ke saath samajh aate hain")
    assert should_extract("Please reply short mein")
    assert should_extract("Mujhe ye style pasand nahi hai")


def test_merge_profiles_preserves_existing_preferences():
    old = empty_profile()
    old["likes"] = ["Python"]
    merged = merge_profiles(old, {"likes": ["Python", "RAG"]})
    assert merged["likes"] == ["Python", "RAG"]
