from concurrent.futures import ThreadPoolExecutor

import pytest

from pawchive_dl import PawchiveDL
from pawchive_dl.__main__ import build_output_templates, parse_args
from pawchive_dl.links import extract_links, update_links_file
from pawchive_dl.models import Creator, Post


POST_URL = "https://pawchive.pw/fanbox/user/42/post/123"


def make_post(post_id: str = "123", content: str = "") -> Post:
    return Post(
        {
            "post": {
                "id": post_id,
                "user": "42",
                "service": "fanbox",
                "title": f"Title {post_id}",
                "content": content,
                "added": "2025-01-01T00:00:00",
                "published": "2025-01-01T00:00:00",
                "edited": "2025-01-01T00:00:00",
            }
        }
    )


def update(path, post_id: str, links, *, service: str = "fanbox", creator_id: str = "42") -> None:
    update_links_file(
        str(path),
        service=service,
        creator_id=creator_id,
        post_id=post_id,
        title=f"Title {post_id}",
        original_url=f"https://pawchive.pw/{service}/user/{creator_id}/post/{post_id}",
        links=links,
    )


def test_extracts_link_text_and_url_with_nested_tags_and_entities():
    html = '<p><a href="https://example.com/a?x=1&amp;y=2">Read <strong>this &amp; that</strong></a></p>'

    assert extract_links(html, POST_URL) == [
        ("Read this & that", "https://example.com/a?x=1&y=2")
    ]


def test_extracts_relative_links_as_absolute_urls():
    links = extract_links('<a href="../about?x=1&amp;y=2">About</a>', POST_URL)

    assert links == [("About", "https://pawchive.pw/fanbox/user/42/about?x=1&y=2")]


def test_uses_url_as_display_text_when_anchor_has_no_text():
    assert extract_links('<a href="/terms"></a>', POST_URL) == [
        ("https://pawchive.pw/terms", "https://pawchive.pw/terms")
    ]


def test_empty_href_resolves_to_post_url_and_malformed_href_is_skipped():
    links = extract_links('<a href>Current page</a><a href="http://[bad">Broken</a>', POST_URL)

    assert links == [("Current page", POST_URL)]


def test_filters_non_web_schemes_and_anchors_without_href():
    html = (
        '<a href="javascript:alert(1)">js</a><a href="data:text/plain,x">data</a>'
        '<a href="mailto:a@example.com">mail</a><a href="ftp://example.com">ftp</a>'
        '<a>no href</a><a href="https://example.com">web</a>'
    )

    assert extract_links(html, POST_URL) == [("web", "https://example.com")]


def test_deduplicates_exact_records_but_keeps_different_labels():
    html = (
        '<a href="https://example.com">Same</a>'
        '<a href="https://example.com">Same</a>'
        '<a href="https://example.com">Different label</a>'
        '<a href="https://second.example">Second</a>'
    )

    assert extract_links(html, POST_URL) == [
        ("Same", "https://example.com"),
        ("Different label", "https://example.com"),
        ("Second", "https://second.example"),
    ]


def test_multiple_posts_append_to_one_creator_file(tmp_path):
    path = tmp_path / "Creator A" / "links.md"
    update(path, "1", [("First", "https://example.com/1")])
    update(path, "2", [("Second", "https://example.com/2")])

    content = path.read_text(encoding="utf-8")
    assert content.count("<!-- pawchive-dl:post:") == 2
    assert "## Title 1" in content and "## Title 2" in content
    assert content.index("## Title 1") < content.index("## Title 2")


def test_reprocessing_post_updates_its_original_section(tmp_path):
    path = tmp_path / "links.md"
    update(path, "1", [("Old", "https://example.com/old")])
    update(path, "2", [("Other", "https://example.com/other")])
    update(path, "1", [("New", "https://example.com/new")])

    content = path.read_text(encoding="utf-8")
    assert content.count("<!-- pawchive-dl:post:fanbox:42:1 -->") == 1
    assert "https://example.com/old" not in content
    assert "[New](https://example.com/new)" in content
    assert "[Other](https://example.com/other)" in content


def test_successful_empty_extraction_removes_only_that_post(tmp_path):
    path = tmp_path / "links.md"
    update(path, "1", [("Old", "https://example.com/old")])
    update(path, "2", [("Keep", "https://example.com/keep")])

    update(path, "1", [])

    content = path.read_text(encoding="utf-8")
    assert "<!-- pawchive-dl:post:fanbox:42:1 -->" not in content
    assert "<!-- pawchive-dl:post:fanbox:42:2 -->" in content
    assert "https://example.com/keep" in content


def test_post_identity_includes_service_creator_and_post(tmp_path):
    path = tmp_path / "links.md"
    update(path, "1", [("A", "https://example.com/a")])
    update(path, "1", [("B", "https://example.com/b")], service="patreon")
    update(path, "1", [("C", "https://example.com/c")], creator_id="99")

    content = path.read_text(encoding="utf-8")
    assert content.count("<!-- pawchive-dl:post:") == 3


def test_concurrent_writes_to_same_file_keep_all_posts(tmp_path):
    path = tmp_path / "links.md"
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda index: update(path, str(index), [(str(index), f"https://example.com/{index}")]), range(24)))

    content = path.read_text(encoding="utf-8")
    assert content.count("<!-- pawchive-dl:post:") == 24
    for index in range(24):
        assert f"https://example.com/{index}" in content


def test_failed_post_request_does_not_remove_existing_links(tmp_path):
    path = tmp_path / "fanbox" / "42" / "links.md"
    update(path, "123", [("Existing", "https://example.com/existing")])
    before = path.read_text(encoding="utf-8")
    client = PawchiveDL(path=str(tmp_path), write_links=True, skip_attachments=True)
    client.get_post = lambda *args: None

    client.download_post("fanbox", "42", "123")

    assert path.read_text(encoding="utf-8") == before


def test_extraction_error_does_not_modify_existing_links(tmp_path, monkeypatch):
    path = tmp_path / "fanbox" / "42" / "links.md"
    update(path, "123", [("Existing", "https://example.com/existing")])
    before = path.read_text(encoding="utf-8")
    client = PawchiveDL(
        path=str(tmp_path),
        write_links=True,
        output_templates={"links": "{service}/{creator_id}/links.md"},
        skip_attachments=True,
        archive_file=str(tmp_path / "processed.txt"),
    )
    client.get_post = lambda *args: make_post()
    client.get_creator_profile = lambda *args: Creator("42", "Creator", "fanbox")
    monkeypatch.setattr("pawchive_dl.client.extract_links", lambda *_: (_ for _ in ()).throw(ValueError("parse failed")))

    client.download_post("fanbox", "42", "123")

    assert path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "processed.txt").exists()


def test_links_use_dedicated_default_template(tmp_path):
    templates = build_output_templates(None)
    client = PawchiveDL(path=str(tmp_path), output_templates=templates, write_links=True)

    client.write_post_links(Creator("42", "Creator A", "fanbox"), make_post(content='<a href="/a">A</a>'))

    assert (tmp_path / "fanbox" / "42" / "links.md").exists()


def test_posts_from_same_creator_share_default_links_file(tmp_path):
    templates = build_output_templates(None)
    client = PawchiveDL(path=str(tmp_path), output_templates=templates, write_links=True)
    creator = Creator("42", "Creator A", "fanbox")

    client.write_post_links(creator, make_post("123", '<a href="/one">One</a>'))
    client.write_post_links(creator, make_post("456", '<a href="/two">Two</a>'))

    path = tmp_path / "fanbox" / "42" / "links.md"
    content = path.read_text(encoding="utf-8")
    assert content.count("<!-- pawchive-dl:post:") == 2
    assert "https://pawchive.pw/one" in content
    assert "https://pawchive.pw/two" in content


def test_links_inherit_generic_output_template(tmp_path):
    templates = build_output_templates(["{creator_name}/{filename}"])
    client = PawchiveDL(path=str(tmp_path), output_templates=templates, write_links=True)

    client.write_post_links(Creator("42", "Creator A", "fanbox"), make_post(content='<a href="/a">A</a>'))

    assert (tmp_path / "Creator A" / "links.md").exists()
    assert templates["attachments"] == "{creator_name}/{filename}"
    assert templates["content"] == "{creator_name}/{filename}"
    assert templates["json"] == "{creator_name}/{filename}"


def test_explicit_links_template_overrides_generic_output(tmp_path):
    templates = build_output_templates(
        ["links:{creator_name}/external-links.md", "{creator_name}/{filename}"]
    )
    client = PawchiveDL(path=str(tmp_path), output_templates=templates, write_links=True)

    client.write_post_links(Creator("42", "Creator A", "fanbox"), make_post(content='<a href="/a">A</a>'))

    assert (tmp_path / "Creator A" / "external-links.md").exists()
    assert not (tmp_path / "Creator A" / "links.md").exists()
    assert templates["attachments"] == "{creator_name}/{filename}"


def test_links_template_without_generic_keeps_other_defaults():
    templates = build_output_templates(["links:{creator_name}/external-links.md"])

    assert templates["links"] == "{creator_name}/external-links.md"
    assert templates["attachments"] == PawchiveDL.DEFAULT_OUTPUT_TEMPLATE
    assert templates["content"] == PawchiveDL.DEFAULT_OUTPUT_TEMPLATE
    assert templates["json"] == PawchiveDL.DEFAULT_OUTPUT_TEMPLATE


def test_write_links_is_optional_and_cli_flag_enables_it(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pawchive-dl", "--write-links"])
    assert parse_args().write_links is True

    client = PawchiveDL(path=str(tmp_path), write_links=False)
    assert client.write_links is False


def test_no_link_file_is_created_when_write_links_is_disabled(tmp_path):
    client = PawchiveDL(path=str(tmp_path), write_links=False)
    client.get_post = lambda *args: make_post(content='<a href="/a">A</a>')
    client.get_creator_profile = lambda *args: Creator("42", "Creator A", "fanbox")
    client.download_post_attachments = lambda *args: 0

    client.download_post("fanbox", "42", "123")

    assert not list(tmp_path.rglob("links.md"))


def test_write_links_works_without_content_json_or_attachments(tmp_path):
    client = PawchiveDL(path=str(tmp_path), write_links=True, skip_attachments=True)
    client.get_post = lambda *args: make_post(content='<a href="/only-links">Link</a>')
    client.get_creator_profile = lambda *args: Creator("42", "Creator A", "fanbox")
    client.download_post_attachments = lambda *args: pytest.fail("attachments should be skipped")

    client.download_post("fanbox", "42", "123")

    content = (tmp_path / "fanbox" / "42" / "links.md").read_text(encoding="utf-8")
    assert "https://pawchive.pw/only-links" in content
