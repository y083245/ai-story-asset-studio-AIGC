import { describe, expect, it } from "vitest";

import { resolveAssetStoragePath, resolveAssetUrl } from "@/shared/api/asset-url";

describe("resolveAssetUrl", () => {
  it("keeps browser-safe URLs unchanged", () => {
    expect(resolveAssetUrl("https://cdn.example.com/a.png")).toBe("https://cdn.example.com/a.png");
    expect(resolveAssetUrl("http://cdn.example.com/a.png")).toBe("http://cdn.example.com/a.png");
    expect(resolveAssetUrl("data:image/png;base64,abc")).toBe("data:image/png;base64,abc");
    expect(resolveAssetUrl("blob:https://app.example.com/abc")).toBe("blob:https://app.example.com/abc");
    expect(resolveAssetUrl("/local-storage/projects/p/a.png")).toBe("/local-storage/projects/p/a.png");
  });

  it("converts historical local file URLs and raw storage paths", () => {
    expect(resolveAssetUrl("file:///app/local_storage/projects/p/a.png")).toBe("/local-storage/projects/p/a.png");
    expect(resolveAssetUrl("file:///Users/example/story-asset-studio/backend/local_storage/projects/p/a.png")).toBe(
      "/local-storage/projects/p/a.png"
    );
    expect(resolveAssetUrl("projects/p/a.png")).toBe("/local-storage/projects/p/a.png");
  });

  it("returns undefined for empty values", () => {
    expect(resolveAssetUrl(undefined)).toBeUndefined();
    expect(resolveAssetUrl(null)).toBeUndefined();
    expect(resolveAssetUrl("")).toBeUndefined();
    expect(resolveAssetUrl("   ")).toBeUndefined();
  });
});

describe("resolveAssetStoragePath", () => {
  it("converts local display URLs and historical file URLs to storage paths", () => {
    expect(resolveAssetStoragePath("/local-storage/projects/p/a.png")).toBe("projects/p/a.png");
    expect(resolveAssetStoragePath("file:///app/local_storage/projects/p/a.png")).toBe("projects/p/a.png");
    expect(resolveAssetStoragePath("file:///Users/example/story-asset-studio/backend/local_storage/projects/p/a.png")).toBe(
      "projects/p/a.png"
    );
    expect(resolveAssetStoragePath("projects/p/a.png")).toBe("projects/p/a.png");
  });

  it("does not turn browser-only URLs into backend storage paths", () => {
    expect(resolveAssetStoragePath("https://cdn.example.com/a.png")).toBeUndefined();
    expect(resolveAssetStoragePath("data:image/png;base64,abc")).toBeUndefined();
    expect(resolveAssetStoragePath("blob:https://app.example.com/abc")).toBeUndefined();
  });
});
