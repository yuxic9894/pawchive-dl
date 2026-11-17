import http.cookiejar

import json
import os
import re
import time
from http.cookiejar import LoadError
from typing import Literal
from urllib.parse import parse_qs, urlparse

from requests.exceptions import RequestException

from .downloader import download_file
from .models import Attachment, Creator, FavoriteCreator, FileTemplateVariables, Post
from .session import CustomSession
from .utils import compute_sha256, generate_file_path, get_sha256_hash

OverwriteMode = Literal[False, "soft", True]
# "soft" will not overwrite the file if it has the expected sha256 hash
# NOTE: if two attachments have the same name (and in the same directory) but different sha256 hashes it will overwirte the first file with the second


class PawchiveDL:
    DOMAIN = "https://pawchive.pw"
    FILE_DOMAIN = "https://file.pawchive.pw"
    POST_STEP_SIZE = 50
    URL_PARSE_PATTERN = r"^https://pawchive\.pw/([^/]+)/user/([^/]+)(?:/post/([^/]+))?$"
    DEFAULT_OUTPUT_TEMPLATE = "{service}/{creator_id}/{post_id}/{filename}"

    def __init__(
        self,
        path: str = os.getcwd(),
        output_templates: dict = {
            "attachments": DEFAULT_OUTPUT_TEMPLATE,
            "content": DEFAULT_OUTPUT_TEMPLATE,
            "json": DEFAULT_OUTPUT_TEMPLATE,
        },
        restrict_names: bool = False,
        custom_template_variables: dict = {},
        archive_file: str | None = None,
        force_overwrite: OverwriteMode = "soft",
        max_retries: int = 3,
        post_filters: dict = {},
        attachment_filters: dict = {},
        skip_attachments: bool = False,
        write_content: bool = False,
        write_json: bool = False,
        no_tmp: bool = False,
    ) -> None:
        self.session = CustomSession()
        self.creators_cache: dict[tuple[str, str], Creator] = {}
        self.path = path
        self.output_templates = output_templates
        self.restrict_names = restrict_names
        self.custom_template_variables = custom_template_variables
        self.force_overwrite = force_overwrite
        self.max_retries = max_retries
        self.post_filters = post_filters
        self.attachment_filters = attachment_filters
        self.skip_attachments = skip_attachments
        self.write_content = write_content
        self.write_json = write_json
        self.no_tmp = no_tmp

        self.archive_file = archive_file
        self.archived_posts = []
        self.load_archive_file()

    def load_archive_file(self) -> None:
        if self.archive_file and os.path.isfile(self.archive_file):
            with open(self.archive_file, "r") as f:
                self.archived_posts.extend(f"{parsed_url['service']}/user/{parsed_url['creator_id']}/post/{parsed_url['post_id']}" for line in f if (parsed_url := self.parse_url(line.strip())))

    def write_archive_file(self, service: str, creator_id: str, post_id: str) -> None:
        archive_path = f"{service}/user/{creator_id}/post/{post_id}"
        self.archived_posts.append(archive_path)
        if self.archive_file:
            with open(self.archive_file, "a", encoding="utf-8") as archive:
                archive.write(f"{PawchiveDL.DOMAIN}/{archive_path}\n")

    def parse_url(self, url: str) -> dict | None:
        parsed = urlparse(url)
        url_without_query = parsed._replace(query="", fragment="").geturl()
        match = re.match(PawchiveDL.URL_PARSE_PATTERN, url_without_query)
        if match:
            service, creator_id, post_id = match.groups()
            parsed_url = {"service": service, "creator_id": creator_id, "post_id": post_id}
            search_query = parse_qs(parsed.query).get("q", [None])[0]
            if search_query:
                parsed_url["search_query"] = search_query
            return parsed_url
        return None

    def load_cookies(self, cookies_file: str) -> bool:
        try:
            jar = http.cookiejar.MozillaCookieJar()
            jar.load(cookies_file)
            for cookie in jar:
                self.session.cookies.set_cookie(cookie)
            return True
        except (LoadError, OSError) as e:
            print(f"[Error] Failed to load cookies from {cookies_file}: {e}")
            return False

    def login(self, username: str, password: str) -> bool:
        try:
            url = f"{PawchiveDL.DOMAIN}/account/login"
            response = self.session.post(url, data={"location": "/artists", "username": username, "password": password})
            response.raise_for_status()
            return True
        except RequestException as e:
            print(f"[Error] Unable to login: {e}")
            return False

    def is_logged_in(self) -> bool:
        url = f"{PawchiveDL.DOMAIN}/account"
        response = self.session.get(url)
        return response.ok

    def get_creator_profile(self, service: str, creator_id: str) -> Creator | None:
        try:
            creator = self.creators_cache.get((service, creator_id), None)
            if creator is None:
                url = f"{PawchiveDL.DOMAIN}/api/v1/{service}/user/{creator_id}/profile"
                response = self.session.get(url, headers={"accept": "text/css"})
                response.raise_for_status()
                creator = Creator(**response.json())
                self.creators_cache[(service, creator_id)] = creator
            return creator
        except (RequestException, ValueError) as e:
            print(f"[Error] Failed to fetch creator profile from {url!r}: {e}")
            return None

    def get_creator_post_ids(
        self,
        service: str,
        creator_id: str,
        offset: int = 0,
        search_query: str | None = None,
    ) -> list[str]:
        try:
            url = f"{PawchiveDL.DOMAIN}/api/v1/{service}/user/{creator_id}/posts"
            params = {"o": offset}
            if search_query:
                params["q"] = search_query
            response = self.session.get(url, params=params, headers={"accept": "text/css"})
            response.raise_for_status()
            posts = response.json()
            return [post.get("id") for post in posts]
        except (RequestException, ValueError) as e:
            print(f"[Error] Failed to fetch posts from {url!r}: {e}")
            return []

    def get_all_creator_post_ids(
        self,
        service: str,
        creator_id: str,
        limit: int = 0,
        offset: int = 0,
        search_query: str | None = None,
    ) -> list[str]:
        posts = []
        while True:
            posts_chunk = self.get_creator_post_ids(service, creator_id, offset, search_query)
            posts += posts_chunk
            if len(posts) >= limit and limit > 0:
                posts = posts[:limit]
                break
            if len(posts_chunk) < PawchiveDL.POST_STEP_SIZE:
                break
            offset += PawchiveDL.POST_STEP_SIZE
            time.sleep(0.5)
        return posts

    def get_post(self, service: str, creator_id: str, post_id: str) -> Post | None:
        try:
            url = f"{PawchiveDL.DOMAIN}/api/v1/{service}/user/{creator_id}/post/{post_id}"
            response = self.session.get(url, headers={"accept": "text/css"})
            response.raise_for_status()
            post_api = response.json()
            return Post(post_api)
        except (RequestException, ValueError) as e:
            print(f"[Error] Failed to fetch post from {url!r}: {e}")
            return None

    def get_favorite_creators(self) -> list[FavoriteCreator] | None:
        try:
            url = f"{PawchiveDL.DOMAIN}/api/v1/account/favorites"
            response = self.session.get(url, params={"type": "artist"}, headers={"accept": "text/css"})
            response.raise_for_status()
            creators = response.json()
            return [FavoriteCreator(**creator) for creator in creators]
        except (RequestException, ValueError) as e:
            print(f"[Error] Failed to fetch favorite creators from {url!r}: {e}")
            return None

    def download_favorite_creators(self) -> None:
        if not self.is_logged_in():
            print(f"[Error] You are not logged into {PawchiveDL.DOMAIN!r}")
            return

        creators = self.get_favorite_creators()

        if creators is None:
            return

        for creator in creators:
            post_ids = self.get_all_creator_post_ids(creator.service, creator.id)
            for post_id in post_ids:
                time.sleep(0.5)
                self.download_post(creator.service, creator.id, post_id)

    def download_url(self, url: str) -> None:
        parsed_url = self.parse_url(url)

        if parsed_url is None:
            print("Invalid URL:" + url)
            return

        if parsed_url["post_id"]:
            self.download_post(parsed_url["service"], parsed_url["creator_id"], parsed_url["post_id"])
        else:
            post_ids = self.get_all_creator_post_ids(
                parsed_url["service"],
                parsed_url["creator_id"],
                search_query=parsed_url.get("search_query"),
            )
            for post_id in post_ids:
                time.sleep(0.5)
                self.download_post(parsed_url["service"], parsed_url["creator_id"], post_id)

    def download_post(self, service: str, creator_id: str, post_id: str) -> None:
        print(f"[downloading] Post URL: {PawchiveDL.DOMAIN}/{service}/user/{creator_id}/post/{post_id}")

        if f"{service}/user/{creator_id}/post/{post_id}" in self.archived_posts:
            print(f"[info] Post {post_id!r} already archived. Skipping.")
            return

        post = self.get_post(service, creator_id, post_id)

        if post is None:
            return

        if self.post_matches_filters(post):
            print(f"[info] Post {post.id!r} matched 1 or more post filters. Skipping.")
            return

        printable_title = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", post.title)[:50]
        print(f"[downloading] Post: {printable_title}")

        creator = self.get_creator_profile(post.service, post.user)
        if creator is None:
            return

        post_errors = 0

        if self.write_json:
            try:
                self.write_post_json(creator, post)
            except Exception as e:
                print(f"[Error] Failed to write post json: {e}")
                post_errors += 1

        if self.write_content:
            try:
                self.write_post_content(creator, post)
            except Exception as e:
                print(f"[Error] Failed to write post content: {e}")
                post_errors += 1

        if self.skip_attachments:
            print("[info] Skipping Post attachments.")
        else:
            post_errors += self.download_post_attachments(creator, post)

        if post_errors == 0:
            self.write_archive_file(post.service, post.user, post.id)

    def download_post_attachments(self, creator: Creator, post: Post):
        if not post.attachments:
            return 0

        print(f"[downloading] Attachments: {len(post.attachments)}")

        attachment_errors = 0

        for attachment in post.attachments:
            if self.attachment_matches_filters(attachment):
                print("[info] Attachment matched 1 or more attachment filters. Skipping.")
                continue

            template_variables = FileTemplateVariables(creator, post, attachment)

            file_path = generate_file_path(
                self.path,
                self.output_templates.get("attachments", self.DEFAULT_OUTPUT_TEMPLATE),
                template_variables.to_dict(self.custom_template_variables),
                self.restrict_names,
            )
            expected_sha256 = template_variables.sha256

            if os.path.exists(file_path):
                actual_sha256 = get_sha256_hash(file_path)

                if self.force_overwrite is False:
                    print(f"[info] File already exists at {file_path}")
                    if expected_sha256 != actual_sha256:
                        print(f'[warning] File sha256 mismatch. Expected "{expected_sha256}" recieved"{actual_sha256}"')
                    continue

                elif self.force_overwrite == "soft" and expected_sha256 == actual_sha256:
                    print(f"[info] File already exists with matching sha256 at {file_path}")
                    continue

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            url = f"{PawchiveDL.FILE_DOMAIN}/data{attachment.path}?f={attachment.name}"

            for _ in range(self.max_retries):
                try:
                    download_file(self.session, url, file_path, temp_file=not self.no_tmp)
                    break
                except Exception as e:
                    print(f"[Error] Failed to download attachment from {url!r}: {e}")
                    attachment_errors += 1
            else:
                print(f"[Error] All {self.max_retries} download reties failed")
                attachment_errors += 1
                continue

            actual_sha256 = get_sha256_hash(file_path)
            if expected_sha256 != actual_sha256:
                print(f"[Error] File downloaded with incorrect SHA-256. Expected: {expected_sha256} Actual: {actual_sha256}")
                attachment_errors += 1

        return attachment_errors

    def write_post_json(self, creator: Creator, post: Post) -> None:
        print("[writing] Post Json")

        sha256 = compute_sha256(json.dumps(post.json))
        attachment = Attachment(name=f"{post.id}.json", path=f"{sha256}.json")
        template_variables = FileTemplateVariables(creator, post, attachment)
        file_path = generate_file_path(
            self.path,
            self.output_templates.get("json", self.DEFAULT_OUTPUT_TEMPLATE),
            template_variables.to_dict(self.custom_template_variables),
            self.restrict_names,
        )
        expected_sha256 = template_variables.sha256

        if os.path.exists(file_path):
            actual_sha256 = get_sha256_hash(file_path)

            if self.force_overwrite is False:
                print(f"[info] File already exists at {file_path}")
                if expected_sha256 != actual_sha256:
                    print(f'[warning] File sha256 mismatch. Expected "{expected_sha256}" recieved"{actual_sha256}"')
                return

            elif self.force_overwrite == "soft" and expected_sha256 == actual_sha256:
                print(f"[info] File already exists with matching sha256 at {file_path}")
                return

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        print(f"[writing] Destination: {file_path!r}")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(post.json, f, indent=4)

    def write_post_content(self, creator: Creator, post: Post) -> None:
        print("[writing] Post Content")

        sha256 = compute_sha256(post.content)
        attachment = Attachment(name="content.html", path=f"{sha256}.html")
        template_variables = FileTemplateVariables(creator, post, attachment)
        file_path = generate_file_path(
            self.path,
            self.output_templates.get("content", self.DEFAULT_OUTPUT_TEMPLATE),
            template_variables.to_dict(self.custom_template_variables),
            self.restrict_names,
        )
        expected_sha256 = template_variables.sha256

        if os.path.exists(file_path):
            actual_sha256 = get_sha256_hash(file_path)

            if self.force_overwrite is False:
                print(f"[info] File already exists at {file_path}")
                if expected_sha256 != actual_sha256:
                    print(f'[warning] File sha256 mismatch. Expected "{expected_sha256}" recieved"{actual_sha256}"')
                return

            elif self.force_overwrite == "soft" and expected_sha256 == actual_sha256:
                print(f"[info] File already exists with matching sha256 at {file_path}")
                return

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        print(f"[writing] Destination: {file_path!r}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(post.content)

    def attachment_matches_filters(self, attachment) -> bool:
        skip_extensions = self.attachment_filters.get("skip_extensions", None)
        file_ext = os.path.splitext(attachment.name)[-1][1:]

        return bool(skip_extensions and file_ext in skip_extensions)

    def post_matches_filters(self, post: Post) -> bool:
        date_filter = self.post_filters.get("date", {})
        datebefore_filter = self.post_filters.get("datebefore", {})
        dateafter_filter = self.post_filters.get("dateafter", {})
        date_fields = ("added", "edited", "published")

        for field in date_fields:
            post_val = getattr(post, field)
            if (val := date_filter.get(field)) and post_val.date() != val.date():
                return True
            if (val := datebefore_filter.get(field)) and post_val.date() > val.date():
                return True
            if (val := dateafter_filter.get(field)) and post_val.date() < val.date():
                return True

        return False
