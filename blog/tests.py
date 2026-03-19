from typing import override

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from blog.models import Post

User = get_user_model()


class PostModelTest(TestCase):
    def test_create_draft_post(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        post = Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            author=user,
            body="Content",
            status=Post.Status.DRAFT,
        )
        self.assertEqual(post.status, "draft")

    def test_create_published_post(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        post = Post.objects.create(
            title="Published Post",
            slug="published-post",
            author=user,
            body="Content",
            status=Post.Status.PUBLISHED,
        )
        self.assertEqual(post.status, "published")

    def test_published_manager_filters_correctly(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        _ = Post.objects.create(
            title="Draft",
            slug="draft",
            author=user,
            body="Content",
            status=Post.Status.DRAFT,
        )
        pub = Post.objects.create(
            title="Published",
            slug="published",
            author=user,
            body="Content",
            status=Post.Status.PUBLISHED,
        )
        self.assertEqual(list(Post.published.all()), [pub])

    def test_str_returns_title(self) -> None:
        post = Post(title="My Post")
        self.assertEqual(str(post), "My Post")


class BlogListAPITest(TestCase):
    draft: Post  # pyright: ignore[reportUninitializedInstanceVariable]
    published: Post  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        self.draft = Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            author=user,
            body="Draft body",
            status=Post.Status.DRAFT,
        )
        self.published = Post.objects.create(
            title="Published Post",
            slug="published-post",
            author=user,
            body="Published body",
            status=Post.Status.PUBLISHED,
            publish=timezone.now(),
        )

    def test_list_returns_all_posts(self) -> None:
        response = self.client.get("/api/blog/posts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_draft_post_has_tag_draft(self) -> None:
        response = self.client.get("/api/blog/posts/")
        draft = next(p for p in response.json() if p["title"] == "Draft Post")
        self.assertEqual(draft["tag"], "draft")

    def test_published_post_has_tag_published(self) -> None:
        response = self.client.get("/api/blog/posts/")
        pub = next(p for p in response.json() if p["title"] == "Published Post")
        self.assertEqual(pub["tag"], "published")

    def test_draft_post_includes_updated(self) -> None:
        response = self.client.get("/api/blog/posts/")
        draft = next(p for p in response.json() if p["tag"] == "draft")
        self.assertIn("updated", draft)

    def test_published_post_includes_body_and_publish(self) -> None:
        response = self.client.get("/api/blog/posts/")
        pub = next(p for p in response.json() if p["tag"] == "published")
        self.assertIn("body", pub)
        self.assertIn("publish", pub)

    def test_draft_post_excludes_body(self) -> None:
        response = self.client.get("/api/blog/posts/")
        draft = next(p for p in response.json() if p["tag"] == "draft")
        self.assertNotIn("body", draft)

    def test_status_not_in_response(self) -> None:
        """status field should not be exposed — tag replaces it."""
        response = self.client.get("/api/blog/posts/")
        for post in response.json():
            self.assertNotIn("status", post)


class BlogDetailAPITest(TestCase):
    draft: Post  # pyright: ignore[reportUninitializedInstanceVariable]
    published: Post  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def setUp(self) -> None:
        user = User.objects.create_user(username="author", password="pass123!")
        self.draft = Post.objects.create(
            title="Draft Post",
            slug="draft-post",
            author=user,
            body="Draft body",
            status=Post.Status.DRAFT,
        )
        self.published = Post.objects.create(
            title="Published Post",
            slug="published-post",
            author=user,
            body="Published body",
            status=Post.Status.PUBLISHED,
            publish=timezone.now(),
        )

    def test_get_draft_post(self) -> None:
        response = self.client.get(f"/api/blog/post/{self.draft.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "draft")
        self.assertEqual(data["title"], "Draft Post")

    def test_get_published_post(self) -> None:
        response = self.client.get(f"/api/blog/post/{self.published.pk}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tag"], "published")
        self.assertEqual(data["title"], "Published Post")

    def test_get_nonexistent_post_returns_400(self) -> None:
        response = self.client.get("/api/blog/post/99999")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["tag"], "PostNotFoundError")
        self.assertEqual(data["id"], 99999)
