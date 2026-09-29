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
    from bot.gateway.mcp_media import extract_r2_keys

    payload = {
        "matches": [
            {"id": "img-1", "metadata": {"r2_key": "photos/red-crop-top.jpg"}},
            {"id": "img-2", "metadata": {"r2_key": "photos/other.jpg"}},
        ],
        "images": [{"r2_key": "photos/red-crop-top.jpg"}],
    }
    assert extract_r2_keys(payload) == [
        "photos/red-crop-top.jpg",
        "photos/other.jpg",
    ]

def test_mcp_image_extraction_from_tool_message_artifact():
    import base64
    from types import SimpleNamespace

    raw = b"artifact-image"
    result = SimpleNamespace(
        content="image fetched",
        artifact=[
            {
                "type": "image",
                "data": base64.b64encode(raw).decode(),
                "mimeType": "image/jpeg",
            }
        ],
    )
    assert CloudflareMCPClient.extract_images(result) == [(raw, "image/jpeg")]

def test_mcp_standard_image_block_extraction():
    import base64
    raw = b"standard-image"
    block = {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(raw).decode(),
        },
    }
    assert CloudflareMCPClient.extract_images(block) == [(raw, "image/png")]


def test_mcp_image_extraction_from_stringified_json():
    import base64
    import json

    raw = b"stringified-image"
    payload = {
        "content": [
            {
                "type": "image",
                "data": base64.b64encode(raw).decode(),
                "mimeType": "image/jpeg",
            }
        ]
    }
    assert CloudflareMCPClient.extract_images(json.dumps(payload)) == [(raw, "image/jpeg")]


def test_raw_mcp_image_method_is_available():
    client = CloudflareMCPClient("https://example.com/mcp")
    assert callable(client.invoke_raw)
