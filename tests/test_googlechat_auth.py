from app.googlechat.auth import _candidate_audiences, _is_allowed_google_chat_principal


def test_candidate_audiences_accepts_trailing_slash_variants():
    assert _candidate_audiences("https://api.grupooliveirarocha.com/googlechat/") == [
        "https://api.grupooliveirarocha.com/googlechat/",
        "https://api.grupooliveirarocha.com/googlechat",
    ]

    assert _candidate_audiences("https://api.grupooliveirarocha.com/googlechat") == [
        "https://api.grupooliveirarocha.com/googlechat",
        "https://api.grupooliveirarocha.com/googlechat/",
    ]


def test_google_chat_principal_allows_chat_and_gsuiteaddons_accounts():
    assert _is_allowed_google_chat_principal("chat@system.gserviceaccount.com")
    assert _is_allowed_google_chat_principal(
        "service-112073849348@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"
    )
    assert not _is_allowed_google_chat_principal("attacker@example.com")
