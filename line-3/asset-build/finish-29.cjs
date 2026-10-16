// Transfer only new generated pigment onto ancestral bare rock.
// One-shot build: requires the original generated PNG at the destination.
const fs = require('node:fs');
const crypto = require('node:crypto');
const media = require('./png_codec.cjs');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const source='artifacts/line-3/wall-v9.png', destination='artifacts/line-3/wall-v10.png';
const oldBytes=fs.readFileSync(source), generatedBytes=fs.readFileSync(destination);
if(hash(oldBytes)!=='93d6a3a5a41eec8ccc73d02b54750083218b04f9dbe5edc4729d8d5932e88dac') throw Error('Wrong ancestral wall');
if(hash(generatedBytes)!=='4bf2c587ffe40f594ddabf8032dc0fa2a3ae1857732feb60962459a12f98ba9f') throw Error('Original generation required; do not rerun on the finished wall');
const old=media.decode(oldBytes), generated=media.decode(generatedBytes);
const out={...old,pixels:Buffer.from(old.pixels)};
const box=[610,930,220,165], crop=[80,190,1100,820];
let changed=0;
for(let dy=0;dy<box[3];dy++) for(let dx=0;dx<box[2];dx++) {
  const sx=Math.round(crop[0]+dx*crop[2]/box[2]), sy=Math.round(crop[1]+dy*crop[3]/box[3]);
  const si=(sy*generated.width+sx)*3;
  const [r,g,b]=generated.pixels.subarray(si,si+3);
  const charcoal=r<112 && g<88 && b<65;
  const redRegion=(sy>275 && sy<405 && sx>210 && sx<1060) ||
    (sy>665 && sy<765 && ((sx>140 && sx<405) || (sx>850 && sx<1110)));
  const red=redRegion && r>85 && r>g*1.6 && r-b>55 && g<130;
  const bowlRegion=sy>750 && sy<866 && ((sx>105 && sx<450) || (sx>800 && sx<1160));
  const yellow=bowlRegion && r>120 && r-g>52 && g-b>38 && g>75 && g<155;
  if(!charcoal && !red && !yellow) continue;
  const color=charcoal?[39,29,21]:red?[150,62,28]:[183,117,41];
  const alpha=charcoal?Math.min(.84,(155-r)/85):red?.72:.58;
  const i=((box[1]+dy)*old.width+box[0]+dx)*3;
  for(let c=0;c<3;c++) out.pixels[i+c]=Math.round(old.pixels[i+c]*(1-alpha)+color[c]*alpha);
  if(!old.pixels.subarray(i,i+3).equals(out.pixels.subarray(i,i+3))) changed++;
}
let outside=0;
for(let y=0;y<old.height;y++) for(let x=0;x<old.width;x++) {
  if(x>=box[0] && x<box[0]+box[2] && y>=box[1] && y<box[1]+box[3]) continue;
  const i=(y*old.width+x)*3;
  if(!out.pixels.subarray(i,i+3).equals(old.pixels.subarray(i,i+3))) outside++;
}
if(outside || changed<1000) throw Error('Pigment preservation check failed');
const bytes=media.encode(out), preview=media.thumbnail(out);
if(!media.decode(bytes).pixels.equals(out.pixels) || preview.length>=100000) throw Error('Output check failed');
fs.writeFileSync(destination,bytes);
fs.unlinkSync('artifacts/line-3/wall.png');
fs.symlinkSync('wall-v10.png','artifacts/line-3/wall.png');
fs.writeFileSync('dist/line-3/29.jpg',preview,{flag:'wx'});
const result={source,source_sha256:hash(oldBytes),generated_sha256:hash(generatedBytes),
  output:destination,output_sha256:hash(bytes),patch_xywh:box,generated_crop_xywh:crop,
  changed_pixels:changed,changed_pixels_outside_patch:outside,
  png_dimensions:[old.width,old.height],png_format:'RGB PNG',png_bytes:bytes.length,
  jpeg_dimensions:[512,512],jpeg_format:'JPEG',jpeg_bytes:preview.length,
  method:'Threshold-selected generated charcoal, red ochre and bowl ochre blended only onto bare lower rock.'};
fs.writeFileSync('line-3/asset-build/preservation-29.json',JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result,null,2));
