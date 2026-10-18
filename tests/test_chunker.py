import pytest
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core import chunker
from app.core.chunker import chunk_document, pick_params
from app.core.parsers import Section


@pytest.fixture(autouse=True)
def offline_splitter(monkeypatch):
    # Real code measures tokens with tiktoken (needs a one-time download).
    # Tests use a character splitter (~4 chars per token) so they run offline.
    monkeypatch.setattr(
        chunker, "_splitter",
        lambda size, overlap: RecursiveCharacterTextSplitter(
            chunk_size=size * 4, chunk_overlap=overlap * 4))


def test_overlap_is_clamped_below_size():
    assert pick_params([Section("x")], "text", 100, 300) == (100, 99)


def test_default_overlap_is_one_eighth():
    assert pick_params([Section("x")], "text", 400, None) == (400, 50)


def test_defaults_by_document_kind():
    assert pick_params([Section("a" * 100)], "markdown", None, None) == (400, 50)
    assert pick_params([Section("a" * 100)], "text", None, None) == (250, 30)    # slide-like
    assert pick_params([Section("a" * 2000)], "text", None, None) == (450, 60)   # long notes


def test_markdown_keeps_heading_breadcrumb():
    md = "# Week 1\n\n## Gradient descent\n\n" + "Gradient descent updates parameters using the loss gradient. " * 4
    chunks = chunk_document([Section(md)], "markdown")
    assert chunks
    assert chunks[0].section == "Week 1 > Gradient descent"
    assert chunks[0].page is None


def test_pages_keep_numbers_and_tiny_fragments_are_dropped():
    sections = [
        Section("Page one has a reasonably long sentence about neural networks and training.", 1),
        Section("tiny", 2),
        Section("", 3),
    ]
    chunks = chunk_document(sections, "text")
    assert [c.page for c in chunks] == [1]


def test_long_text_is_split_into_several_chunks():
    text = " ".join(f"Sentence number {i} explains one small idea clearly." for i in range(200))
    chunks = chunk_document([Section(text)], "text", size=100, overlap=10)
    assert len(chunks) > 3
    assert all(len(c.text) <= 100 * 4 + 20 for c in chunks)
