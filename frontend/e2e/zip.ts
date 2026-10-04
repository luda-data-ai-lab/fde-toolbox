import { inflateRawSync } from "node:zlib";

/** Concatenated contents of the ZIP entries whose names start with `prefix` (stored or deflated), numeric character references decoded. */
export function zipText(zip: Buffer, prefix: string): string {
  const eocd = zip.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  let p = zip.readUInt32LE(eocd + 16);
  let text = "";
  for (let i = zip.readUInt16LE(eocd + 10); i > 0; i--) {
    const nameLen = zip.readUInt16LE(p + 28);
    if (zip.toString("utf-8", p + 46, p + 46 + nameLen).startsWith(prefix)) {
      const local = zip.readUInt32LE(p + 42);
      const start =
        local +
        30 +
        zip.readUInt16LE(local + 26) +
        zip.readUInt16LE(local + 28);
      const data = zip.subarray(start, start + zip.readUInt32LE(p + 20));
      text += (
        zip.readUInt16LE(p + 10) === 8 ? inflateRawSync(data) : data
      ).toString("utf-8");
    }
    p += 46 + nameLen + zip.readUInt16LE(p + 30) + zip.readUInt16LE(p + 32);
  }
  return text.replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n: string) =>
    String.fromCodePoint(
      n[0].toLowerCase() === "x" ? parseInt(n.slice(1), 16) : Number(n),
    ),
  );
}
