import { match } from "ts-pattern";
import type {
  DraftPostSchema,
  PublishedPostSchema,
  PostNotFoundError,
} from "../generated/types.gen";

// Local alias for the post union type.
// The Hey API generator expresses this inline in response types;
// we define it here for readability.
type PostSchema = DraftPostSchema | PublishedPostSchema;

// Placeholder error types — replace with generated types once backend is built.
// TODO: replace AuthError/ValidationError with generated types once backend is built
type AuthError = { type: "auth_error"; message: string };
type ValidationError = {
  type: "validation_error";
  field: string;
  message: string;
};
type ApiError = PostNotFoundError | AuthError | ValidationError;

// Example 1: match on the PostSchema discriminated union only.
// Demonstrates: ts-pattern matches on the `status` discriminant field.
// The `status` field narrows the type — `p.updated` is only available on DraftPostSchema,
// `p.publish` only on PublishedPostSchema.
function describePost(post: PostSchema): string {
  return match(post)
    .with(
      { status: "DF" },
      (p) => `Draft: ${p.title}, last updated ${p.updated}`,
    )
    .with(
      { status: "PB" },
      (p) => `Published: ${p.title} on ${p.publish ?? "TBD"}`,
    )
    .exhaustive();
}

// Example 2: match on errors only.
// Demonstrates: multi-error matching — PostNotFoundError uses `tag` as its discriminant
// (generated from the backend's TaggedSchema), while local placeholder errors use `type`.
// `.exhaustive()` ensures all three error types are handled.
function describeError(error: ApiError): string {
  return match(error)
    .with(
      { tag: "post_not_found" },
      (e) => `Post ${e.id} not found: ${e.detail}`,
    )
    .with({ type: "auth_error" }, (e) => `Auth error: ${e.message}`)
    .with(
      { type: "validation_error" },
      (e) => `Validation error on ${e.field}: ${e.message}`,
    )
    .exhaustive();
}

// Example 3: combined success + error match in one exhaustive chain.
// Demonstrates: the realistic usage pattern — handle all success variants and all error
// variants together. ts-pattern narrows each branch precisely.
// Remove a `.with(...)` arm to see the TypeScript compile error from `.exhaustive()`.
function handlePostResult(result: PostSchema | ApiError): string {
  return match(result)
    .with({ status: "DF" }, (p) => `Draft: ${p.title}`)
    .with({ status: "PB" }, (p) => `Published: ${p.title}`)
    .with(
      { tag: "post_not_found" },
      (e) => `Not found: post ${e.id} — ${e.detail}`,
    )
    .with({ type: "auth_error" }, (e) => `Unauthorized: ${e.message}`)
    .with({ type: "validation_error" }, (e) => `Bad input on ${e.field}`)
    .exhaustive();
}
