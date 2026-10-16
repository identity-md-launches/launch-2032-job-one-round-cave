// Place the image tool's new pigment on unpainted rock; retain all earlier pixels.
const fs = require('node:fs');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const media = require('../line-1/media/finish-wall.cjs');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function rgbaPng(bytes) {
  if (!bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))) throw Error('PNG required');
  let width, height, channels, parts = [];
  for (let at = 8; at < bytes.length;) {
    const size = bytes.readUInt32BE(at), kind = bytes.toString('ascii', at + 4, at + 8);
    const data = bytes.subarray(at + 8, at + 8 + size);
    if (kind === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      if (data[8] !== 8 || data[9] !== 6 || data[12] !== 0 || width > 2048 || height > 2048)
        throw Error('small 8-bit noninterlaced RGBA PNG required');
      channels = 4;
    }
    if (kind === 'IDAT') parts.push(data);
    at += 12 + size;
    if (kind === 'IEND') break;
  }
  const stride = width * channels, packed = zlib.inflateSync(Buffer.concat(parts));
  if (packed.length !== height * (stride + 1)) throw Error('bad raster length');
  const pixels = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y++) {
    const filter = packed[y * (stride + 1)];
    if (filter > 4) throw Error('bad PNG filter');
    for (let x = 0; x < stride; x++) {
      const i = y * stride + x;
      const a = x >= channels ? pixels[i - channels] : 0;
      const b = y ? pixels[i - stride] : 0;
      const c = y && x >= channels ? pixels[i - stride - channels] : 0;
      const p = a + b - c;
      const predictor = [0, a, b, Math.floor((a + b) / 2),
        Math.abs(p - a) <= Math.abs(p - b) && Math.abs(p - a) <= Math.abs(p - c) ? a
          : Math.abs(p - b) <= Math.abs(p - c) ? b : c][filter];
      pixels[i] = (packed[y * (stride + 1) + 1 + x] + predictor) & 255;
    }
  }
  return {width, height, pixels};
}

const previousBytes = fs.readFileSync('artifacts/gathering/wall-v9.png');
const generatedBytes = fs.readFileSync('artifacts/gathering/wall-v10.png');
const previous = media.decode(previousBytes), generated = rgbaPng(generatedBytes);
if (previous.width !== 1254 || previous.height !== 1254 || generated.width !== 1536 || generated.height !== 1024)
  throw Error('unexpected wall or generated dimensions');
const generatedHash = sha(generatedBytes);
const output = {...previous, pixels: Buffer.from(previous.pixels)};
const box = [925, 135, 220, 205];
const crop = [350, 120, 860, 800];
let changed = 0;
for (let y = box[1]; y < box[1] + box[3]; y++) for (let x = box[0]; x < box[0] + box[2]; x++) {
  const sx = Math.floor(crop[0] + (x - box[0] + .5) * crop[2] / box[2]);
  const sy = Math.floor(crop[1] + (y - box[1] + .5) * crop[3] / box[3]);
  const j = (sy * generated.width + sx) * 4;
  const r = generated.pixels[j], g = generated.pixels[j + 1], b = generated.pixels[j + 2];
  const sourceAlpha = generated.pixels[j + 3];
  // Drop the generated glow. The remaining flecks supply the handmade silhouette.
  if (sourceAlpha < 105) continue;
  const pigment = r > g * 1.3 && r > b * 1.3 ? [145, 62, 30]
    : r > 175 && g > 165 && b > 140 ? [218, 207, 173]
      : r > g * 1.03 && g > b * 1.12 ? [180, 128, 55] : [46, 36, 26];
  const alpha = Math.min(.69, (sourceAlpha - 75) / 260);
  const i = (y * output.width + x) * 3;
  for (let c = 0; c < 3; c++)
    output.pixels[i + c] = Math.round(previous.pixels[i + c] * (1 - alpha) + pigment[c] * alpha);
  if (!output.pixels.subarray(i, i + 3).equals(previous.pixels.subarray(i, i + 3))) changed++;
}
if (changed < 1200) throw Error('new mark is missing');
let outside = 0;
const protectedHash = crypto.createHash('sha256');
for (let y = 0; y < output.height; y++) for (let x = 0; x < output.width; x++) {
  if (x >= box[0] && x < box[0] + box[2] && y >= box[1] && y < box[1] + box[3]) continue;
  const i = (y * output.width + x) * 3;
  if (!output.pixels.subarray(i, i + 3).equals(previous.pixels.subarray(i, i + 3))) outside++;
  protectedHash.update(output.pixels.subarray(i, i + 3));
}
if (outside) throw Error('previous painting changed outside the new mark');
const wall = media.encode(output), preview = media.thumbnail(output);
if (!media.decode(wall).pixels.equals(output.pixels) || preview.length > 100000) throw Error('encoding failure');
fs.writeFileSync('artifacts/gathering/wall-v10.png', wall);
fs.writeFileSync('dist/gathering/29.jpg', preview);
fs.unlinkSync('artifacts/gathering/wall.png');
fs.symlinkSync('wall-v10.png', 'artifacts/gathering/wall.png');
const report = {inherited_wall_sha256: sha(previousBytes), generated_mark_sha256: generatedHash,
  output_sha256: sha(wall), mark_rectangle: box, changed_pixels_inside: changed,
  pixels_changed_outside: outside, protected_rgb_sha256: protectedHash.digest('hex'),
  method: 'Image-tool pigment flecks composited on bare upper-right rock; inherited pixels retained outside mark.',
  png_dimensions: [1254, 1254], png_format: 'RGB PNG', jpeg_dimensions: [512, 512],
  jpeg_bytes: preview.length};
fs.writeFileSync('gathering/preservation-29.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
