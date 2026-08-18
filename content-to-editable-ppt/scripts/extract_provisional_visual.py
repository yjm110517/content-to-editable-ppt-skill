from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from PIL import Image
from schema_utils import ContractError,error,load_json,validate_schema

SCHEMA_DIR=Path(__file__).resolve().parents[1]/"schemas"
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--raw-layer",type=Path,required=True);p.add_argument("--element-map",type=Path,required=True);p.add_argument("--element-id",required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--record",type=Path,required=True);args=p.parse_args()
    try:
        if args.output.exists() or args.record.exists():raise ContractError([error("$.output","output exists","overwrite_forbidden")])
        element_map=load_json(args.element_map);validate_schema("design_element_map",element_map,SCHEMA_DIR);items=[item for item in element_map["elements"] if item["element_id"]==args.element_id]
        if len(items)!=1 or items[0]["reconstruction_class"] not in {"reusable_raster","generated_foreground"}:raise ContractError([error("$.element_id","element is not extractable raster","invalid_extraction_target")])
        image=Image.open(args.raw_layer).convert("RGBA");box=items[0]["normalized_bbox"];left=box["x"]*image.width//10000;top=box["y"]*image.height//10000;right=(box["x"]+box["w"])*image.width//10000;bottom=(box["y"]+box["h"])*image.height//10000
        crop=image.crop((left,top,right,bottom));pixels=crop.load();corners=[pixels[0,0],pixels[crop.width-1,0],pixels[0,crop.height-1],pixels[crop.width-1,crop.height-1]];base=tuple(sum(value[channel] for value in corners)//4 for channel in range(3));spread=max(max(abs(value[channel]-base[channel]) for value in corners) for channel in range(3))
        separation="clean_local_background"
        if spread<=12:
            changed=0
            for y in range(crop.height):
                for x in range(crop.width):
                    r,g,b,a=pixels[x,y];distance=max(abs(r-base[0]),abs(g-base[1]),abs(b-base[2]));alpha=0 if distance<=18 else min(255,(distance-18)*8);pixels[x,y]=(r,g,b,min(a,alpha));changed+=alpha==0
            if changed>crop.width*crop.height//20:separation="transparent"
        if crop.width<64 or crop.height<64 or separation!="transparent":raise ContractError([error("$.crop_bbox","visual is not safely separable","foreground_extraction_failed")])
        args.output.parent.mkdir(parents=True,exist_ok=True);crop.save(args.output,format="PNG",compress_level=9)
        record={"schema_version":"1.0","artifact_type":"provisional_visual_asset_record","deck_id":element_map["deck_id"],"slide_id":element_map["slide_id"],"element_id":args.element_id,"visual_ref":items[0]["source_ref"],"generated_layer_sha256":sha(args.raw_layer),"crop_bbox":box,"asset_path":args.output.name,"asset_sha256":sha(args.output),"background_separation":separation,"extraction_quality":"pass","status":"provisional"};validate_schema("provisional_visual_asset_record",record,SCHEMA_DIR);temp=args.record.with_suffix(args.record.suffix+".tmp");temp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(temp,args.record);print(json.dumps({"status":"ok","record":str(args.record)},ensure_ascii=False));return 0
    except Exception as exc:
        errors=exc.errors if isinstance(exc,ContractError) else [{"path":"$","code":"extraction_error","message":str(exc)}];print(json.dumps({"status":"error","errors":errors},ensure_ascii=False));return 4
if __name__=="__main__":raise SystemExit(main())
