from app.config import csv_emails


def test_csv_emails_normalizes_and_dedupes():
    assert csv_emails(" A@x.com, b@x.com ,A@X.com") == {"a@x.com", "b@x.com"}


def test_csv_emails_empty():
    assert csv_emails("") == set()
    assert csv_emails("  ,  ") == set()
