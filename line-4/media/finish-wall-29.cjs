// Preserve ancestor pixels, retaining only the image tool's new linked rings.
// No network or configuration access. Run once against the raw generated edit.
const fs=require('node:fs'), crypto=require('node:crypto');
const {decode,encode,thumbnail}=require('../../line-1/media/finish-wall.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const base=fs.readFileSync('artifacts/line-4/wall-v9.png');
const previous=JSON.parse(fs.readFileSync('dist/line-4/28.json'));
if(previous.image!=='https://api.imd.fun/artifacts/'+sha(base)) throw Error('ancestor hash mismatch');
const raw=fs.readFileSync('artifacts/line-4/wall-v10.png');
const old=decode(base), gen=decode(raw), out={...old,pixels:Buffer.from(old.pixels)};
const clamp=n=>Math.max(0,Math.min(1,n));
const bounds=[975,396,1116,493];
function mask(x,y) {
 const a=Math.abs(Math.hypot((x-1023)/39,(y-435)/29)-1)*29;
 const b=Math.abs(Math.hypot((x-1072)/35,(y-454)/29)-1)*29;
 return clamp((12-Math.min(a,b))/3);
}
let changed=0,outside=0;
for(let y=0;y<old.height;y++) for(let x=0;x<old.width;x++) {
 const at=(y*old.width+x)*3,inside=x>=bounds[0]&&x<=bounds[2]&&y>=bounds[1]&&y<=bounds[3];
 const a=inside?mask(x,y):0;
 for(let c=0;c<3;c++) out.pixels[at+c]=Math.round(old.pixels[at+c]*(1-a)+gen.pixels[at+c]*a);
 if(!out.pixels.subarray(at,at+3).equals(old.pixels.subarray(at,at+3))) {
  changed++; if(!a||!inside) outside++;
 }
}
if(changed<1000||outside) throw Error('preservation failure');
const png=encode(out), jpg=thumbnail(out);
if(!decode(png).pixels.equals(out.pixels)||jpg.length>100000) throw Error('media check failed');
fs.writeFileSync('artifacts/line-4/wall-v10.png',png);
fs.unlinkSync('artifacts/line-4/wall.png');
fs.linkSync('artifacts/line-4/wall-v10.png','artifacts/line-4/wall.png');
// One JPEG inode is available at both required locations.
fs.writeFileSync('artifacts/line-4/29.jpg',jpg);
fs.linkSync('artifacts/line-4/29.jpg','dist/line-4/29.jpg');
const report={source:'artifacts/line-4/wall-v9.png',source_sha256:sha(base),generated_sha256:sha(raw),
 wall:'artifacts/line-4/wall-v10.png',canonical_wall:'artifacts/line-4/wall.png',sha256:sha(png),
 width:out.width,height:out.height,format:'PNG',mode:'RGB',bytes:png.length,
 preview:'dist/line-4/29.jpg',preview_width:512,preview_height:512,preview_format:'JPEG',preview_bytes:jpg.length,
 preview_sha256:sha(jpg),addition_bounds_inclusive:bounds,changed_pixels:changed,
 changed_pixels_outside_addition:outside,png_roundtrip_passed:true};
fs.writeFileSync('line-4/media-check-29.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
