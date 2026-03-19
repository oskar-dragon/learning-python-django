import { match } from "ts-pattern";
import type {
  BlogApiGetPostError,
  DraftPost,
  PostResponse,
  PublishedPost,
} from "../generated/types.gen";

// Example 1: match on the PostResponse discriminated union.
// Demonstrates: ts-pattern matches on the `tag` discriminant field.
// The `tag` field narrows the type — `p.updated` is only available on DraftPost,
// `p.body` and `p.publish` only on PublishedPost.
function describePost(post: PostResponse): string {
  return match(post)
    .with(
      { tag: "draft" },
      (p) => `Draft: ${p.title}, last updated ${p.updated}`,
    )
    .with(
      { tag: "published" },
      (p) => `Published: ${p.title} on ${p.publish ?? "TBD"}`,
    )
    .exhaustive();
}

// Example 2: match on errors only.
// Uses the generated error union type — domain and framework errors discriminated by tag.
function describeError(error: BlogApiGetPostError): string {
  return match(error)
    .with(
      { tag: "PostNotFoundError" },
      (e) => `Post ${e.id} not found: ${e.detail}`,
    )
    .with({ tag: "ValidationError" }, () => "Invalid request")
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
function handlePostResult(result: PostResponse | BlogApiGetPostError): string {
  return match(result)
    .with({ tag: "draft" }, (p) => `Draft: ${p.title}`)
    .with({ tag: "published" }, (p) => `Published: ${p.title}`)
    .with(
      { tag: "PostNotFoundError" },
      (e) => `Not found: post ${e.id} — ${e.detail}`,
    )
    .with({ tag: "ValidationError" }, () => "Invalid request")
    .with({ tag: "InternalError" }, () => "Something went wrong")
    .exhaustive();
}
