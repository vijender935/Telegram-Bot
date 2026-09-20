from bot.infrastructure.rag_mcp import CloudflareMCPClient


def test_mcp_image_extraction_from_dict():
    import base64

    raw = b"test-image"
    result = {
        "content": [
            {
                "type": "image",
                "data": base64.b64encode(raw).decode(),
                "mimeType": "image/jpeg",
            }
        ]
    }
    assert CloudflareMCPClient.extract_images(result) == [(raw, "image/jpeg")]


def test_safe_url_hides_credentials():
    client = CloudflareMCPClient("https://example.com/mcp?token=secret")
    assert client._safe_url() == "https://example.com/mcp"



def test_extract_r2_keys_from_search_result():
    from bot.gateway.handlers import _extract_r2_keys

    payload = {
        "matches": [
            {"id": "img-1", "metadata": {"r2_key": "photos/red-crop-top.jpg"}},
            {"id": "img-2", "metadata": {"r2_key": "photos/other.jpg"}},
        ],
        "images": [{"r2_key": "photos/red-crop-top.jpg"}],
    }
    assert _extract_r2_keys(payload) == [
        "photos/red-crop-top.jpg",
        "photos/other.jpg",
    ]
