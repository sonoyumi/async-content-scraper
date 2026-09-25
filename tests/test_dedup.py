from scraper.dedup.hasher import ExtractedItem, compute_content_hash


def test_same_content_same_hash_regardless_of_media_order():
    hash_a = compute_content_hash("hello world", ["https://x/1.jpg", "https://x/2.jpg"])
    hash_b = compute_content_hash("hello   world", ["https://x/2.jpg", "https://x/1.jpg"])
    assert hash_a == hash_b


def test_different_text_different_hash():
    hash_a = compute_content_hash("hello", [])
    hash_b = compute_content_hash("goodbye", [])
    assert hash_a != hash_b


def test_extracted_item_falls_back_to_content_hash_as_external_id():
    item = ExtractedItem(external_id="", text="hi", published_at=None, url=None)
    assert item.external_id == item.content_hash
    assert len(item.content_hash) == 64
