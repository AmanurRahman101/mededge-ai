const MAX_PIXELS = 2_800_000;

/** Downscale a phone photo below the server limit, applying EXIF rotation. */
export async function prepareImage(file: File): Promise<File> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file; // Let the server report an unsupported file.
  }
  const pixels = bitmap.width * bitmap.height;
  const scale = pixels > MAX_PIXELS ? Math.sqrt(MAX_PIXELS / pixels) : 1;
  if (scale === 1 && /^image\/(jpeg|png|webp)$/.test(file.type) && file.size < 6_000_000) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.floor(bitmap.width * scale));
  canvas.height = Math.max(1, Math.floor(bitmap.height * scale));
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  if (!blob) return file;
  return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
}
