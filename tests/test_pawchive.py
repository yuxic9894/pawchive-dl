import json
from http.cookiejar import LoadError
from unittest.mock import MagicMock, Mock, patch

import pytest

from pawchive_dl import PawchiveDL
from pawchive_dl.models import Creator, FavoriteCreator, Post

TEST_DATA_PATH = "tests/data"


@pytest.fixture
def pawchive_dl() -> PawchiveDL:
    return PawchiveDL()


@patch("pawchive_dl.session.requests.Session.get")
def test_is_loggedin_true(mock_get, pawchive_dl: PawchiveDL) -> None:
    mock_get.return_value = Mock(ok=True)
    result = pawchive_dl.is_logged_in()
    assert result is True
    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/account",
    )


@patch("pawchive_dl.session.requests.Session.get")
def test_is_loggedin_false(mock_get, pawchive_dl: PawchiveDL) -> None:
    mock_get.return_value = Mock(ok=False)
    result = pawchive_dl.is_logged_in()
    assert result is False
    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/account",
    )


@patch("pawchive_dl.session.requests.Session.get")
def test_get_creator_posts(mock_get, pawchive_dl: PawchiveDL) -> None:
    with open(f"{TEST_DATA_PATH}/creator_posts.json", encoding="utf-8") as f:
        mock_data = json.load(f)

    mock_get.return_value = Mock(json=lambda: mock_data)
    post_ids = pawchive_dl.get_creator_post_ids("SERVICE_123", "USER_123", 0)

    assert len(post_ids) == len(mock_data)
    assert post_ids == [post.get("id") for post in mock_data]
    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/api/v1/SERVICE_123/user/USER_123/posts",
        params={"o": 0},
        headers={"accept": "text/css"},
    )


@patch("pawchive_dl.session.requests.Session.get")
def test_get_creator_posts_with_search_query(mock_get, pawchive_dl: PawchiveDL) -> None:
    mock_get.return_value = Mock(json=lambda: [])

    post_ids = pawchive_dl.get_creator_post_ids(
        "fanbox",
        "73132618",
        search_query="becky",
    )

    assert post_ids == []
    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/api/v1/fanbox/user/73132618/posts",
        params={"o": 0, "q": "becky"},
        headers={"accept": "text/css"},
    )


@patch("pawchive_dl.session.requests.Session.get")
def test_get_post(mock_get, pawchive_dl: PawchiveDL) -> None:
    with open(f"{TEST_DATA_PATH}/post.json", encoding="utf-8") as f:
        mock_data = json.load(f)

    mock_get.return_value = Mock(json=lambda: mock_data)
    post = pawchive_dl.get_post("SERVICE_123", "USER_123", "1103388334")

    assert post == Post(mock_data)
    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/api/v1/SERVICE_123/user/USER_123/post/1103388334",
        headers={"accept": "text/css"},
    )


@patch("pawchive_dl.session.requests.Session.get")
def test_get_post_exception(mock_get, pawchive_dl: PawchiveDL, capsys) -> None:
    mock_get.side_effect = ValueError("Json Error")

    result = pawchive_dl.get_post("SERVICE_123", "USER_123", "1103388334")

    assert result is None

    captured = capsys.readouterr().out
    assert "[Error] Failed to fetch post from" in captured
    assert "Json Error" in captured

    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/api/v1/SERVICE_123/user/USER_123/post/1103388334",
        headers={"accept": "text/css"},
    )


@patch("pawchive_dl.session.requests.Session.get")
def test_get_creator(mock_get, pawchive_dl: PawchiveDL) -> None:
    with open(f"{TEST_DATA_PATH}/creator_profile.json", encoding="utf-8") as f:
        mock_data = json.load(f)

    mock_get.return_value = Mock(json=lambda: mock_data)
    creator = pawchive_dl.get_creator_profile("SERVICE_123", "USER_123")

    assert creator == Creator(**mock_data)
    mock_get.assert_called_once_with(PawchiveDL.DOMAIN + "/api/v1/SERVICE_123/user/USER_123/profile", headers={"accept": "text/css"})


def test_parse_url_match_creator(pawchive_dl: PawchiveDL):
    expected = {"service": "fanbox", "creator_id": "73132618", "post_id": None}
    result = pawchive_dl.parse_url("https://pawchive.pw/fanbox/user/73132618")
    assert result == expected


def test_parse_url_match_post(pawchive_dl: PawchiveDL):
    expected = {"service": "fanbox", "creator_id": "73132618", "post_id": "123"}
    result = pawchive_dl.parse_url("https://pawchive.pw/fanbox/user/73132618/post/123")
    assert result == expected


def test_parse_url_match_creator_with_search_query(pawchive_dl: PawchiveDL):
    expected = {
        "service": "fanbox",
        "creator_id": "73132618",
        "post_id": None,
        "search_query": "becky",
    }
    result = pawchive_dl.parse_url("https://pawchive.pw/fanbox/user/73132618?q=becky")
    assert result == expected


def test_parse_url_no_match(pawchive_dl: PawchiveDL):
    expected = None
    result = pawchive_dl.parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert result == expected


def test_get_all_creator_posts(pawchive_dl: PawchiveDL) -> None:
    with open(f"{TEST_DATA_PATH}/creator_posts.json", encoding="utf-8") as f:
        mock_data_page_1 = json.load(f)
    mock_data_page_2 = mock_data_page_1[:20]
    mock_data = [mock_data_page_1, mock_data_page_2]
    pawchive_dl.get_creator_post_ids = Mock()
    pawchive_dl.get_creator_post_ids.side_effect = mock_data
    result = pawchive_dl.get_all_creator_post_ids(
        "SERVICE_123",
        "USER_123",
    )
    assert result == mock_data_page_1 + mock_data_page_2
    assert pawchive_dl.get_creator_post_ids.call_count == 2


def test_get_all_creator_posts_limit(pawchive_dl: PawchiveDL) -> None:
    with open(f"{TEST_DATA_PATH}/creator_posts.json", encoding="utf-8") as f:
        mock_data_page_1 = json.load(f)
    mock_data_page_2 = mock_data_page_1[:20]
    mock_data = [mock_data_page_1, mock_data_page_2]
    pawchive_dl.get_creator_post_ids = Mock()
    pawchive_dl.get_creator_post_ids.side_effect = mock_data
    result = pawchive_dl.get_all_creator_post_ids(
        "SERVICE_123",
        "USER_123",
        10,
    )
    assert result == mock_data_page_1[:10]
    assert pawchive_dl.get_creator_post_ids.call_count == 1


@patch("pawchive_dl.session.requests.Session.get")
def test_get_favorite_creators(mock_get, pawchive_dl: PawchiveDL) -> None:
    with open(f"{TEST_DATA_PATH}/favorite_creators.json", encoding="utf-8") as f:
        mock_data = json.load(f)

    mock_get.return_value = Mock(json=lambda: mock_data)
    result = pawchive_dl.get_favorite_creators()

    assert result == [FavoriteCreator(**fav) for fav in mock_data]
    mock_get.assert_called_once_with(
        PawchiveDL.DOMAIN + "/api/v1/account/favorites",
        params={"type": "artist"},
        headers={"accept": "text/css"},
    )


@patch("http.cookiejar.MozillaCookieJar")
def test_load_cookies(mock_cookiejar_cls, pawchive_dl: PawchiveDL):
    mock_cookie = MagicMock()
    mock_jar = MagicMock()
    mock_jar.__iter__.return_value = [mock_cookie]
    mock_jar.load = MagicMock()
    mock_cookiejar_cls.return_value = mock_jar

    pawchive_dl.session = MagicMock()
    pawchive_dl.session.cookies.set_cookie = MagicMock()

    result = pawchive_dl.load_cookies("cookies.txt")

    assert result is True
    mock_jar.load.assert_called_once_with("cookies.txt")
    pawchive_dl.session.cookies.set_cookie.assert_called_once_with(mock_cookie)


@patch("http.cookiejar.MozillaCookieJar")
def test_load_cookies_exception(mock_cookiejar_cls, pawchive_dl: PawchiveDL, capsys):
    mock_jar = MagicMock()
    mock_jar.load.side_effect = LoadError()
    mock_cookiejar_cls.return_value = mock_jar

    result = pawchive_dl.load_cookies("cookies.txt")

    assert result is False
    mock_jar.load.assert_called_once_with("cookies.txt")
    captured = capsys.readouterr().out
    assert "[Error] Failed to load cookies from cookies.txt" in captured


@patch("pawchive_dl.session.requests.Session.post")
def test_login_uses_pawchive_web_form(mock_post, pawchive_dl: PawchiveDL) -> None:
    response = Mock()
    mock_post.return_value = response

    assert pawchive_dl.login("username", "password") is True
    mock_post.assert_called_once_with(
        PawchiveDL.DOMAIN + "/account/login",
        data={"location": "/artists", "username": "username", "password": "password"},
    )


def test_archive_round_trip_uses_pawchive_post_url(tmp_path) -> None:
    archive_file = tmp_path / "archive.txt"
    client = PawchiveDL(archive_file=str(archive_file))

    client.write_archive_file("fanbox", "73132618", "123")

    assert archive_file.read_text(encoding="utf-8") == "https://pawchive.pw/fanbox/user/73132618/post/123\n"
    reloaded = PawchiveDL(archive_file=str(archive_file))
    assert "fanbox/user/73132618/post/123" in reloaded.archived_posts
