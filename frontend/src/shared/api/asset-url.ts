export function resolveAssetUrl(value?: string | null): string | undefined {
  const raw = value?.trim();
  if (!raw) return undefined;

  if (/^(https?:|data:|blob:)/i.test(raw)) return raw;
  if (raw.startsWith("/local-storage/")) return raw;

  const normalized = raw.replace(/\\/g, "/");
  const localStorageMarker = "/local_storage/";
  const localStorageIndex = normalized.indexOf(localStorageMarker);
  if (localStorageIndex >= 0) {
    return toLocalStorageUrl(normalized.slice(localStorageIndex + localStorageMarker.length));
  }

  if (normalized.startsWith("local_storage/")) {
    return toLocalStorageUrl(normalized.slice("local_storage/".length));
  }

  if (normalized.startsWith("file://")) return undefined;

  if (normalized.startsWith("projects/")) return toLocalStorageUrl(normalized);
  if (normalized.startsWith("/projects/")) return toLocalStorageUrl(normalized.slice(1));

  return normalized;
}

export function resolveAssetStoragePath(value?: string | null): string | undefined {
  const raw = value?.trim();
  if (!raw) return undefined;

  if (/^(https?:|data:|blob:)/i.test(raw)) return undefined;

  const normalized = raw.replace(/\\/g, "/");
  if (normalized.startsWith("/local-storage/")) {
    return normalized.slice("/local-storage/".length);
  }

  const localStorageMarker = "/local_storage/";
  const localStorageIndex = normalized.indexOf(localStorageMarker);
  if (localStorageIndex >= 0) {
    return stripLeadingSlash(normalized.slice(localStorageIndex + localStorageMarker.length));
  }

  if (normalized.startsWith("local_storage/")) {
    return stripLeadingSlash(normalized.slice("local_storage/".length));
  }

  if (normalized.startsWith("file://")) return undefined;
  if (normalized.startsWith("/projects/")) return normalized.slice(1);

  return stripLeadingSlash(normalized);
}

function toLocalStorageUrl(path: string): string {
  return `/local-storage/${stripLeadingSlash(path)}`;
}

function stripLeadingSlash(path: string): string {
  return path.replace(/^\/+/, "");
}
