from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from canonical_artifact import canonical_sha256
from schema_utils import ContractError,error,load_json,validate_schema
SCHEMA_DIR=Path(__file__).resolve().parents[1]/"schemas"
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def write_once(path:Path,value:dict):
    if path.exists():raise ContractError([error(str(path),"immutable output exists","overwrite_forbidden")])
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(tmp,path)
def prepare_page(args):
    package=load_json(args.prompt_package);reference=load_json(args.style_reference_record);lock=load_json(args.runtime_lock);validate_schema("deck_prompt_package",package,SCHEMA_DIR);validate_schema("style_anchor_reference_record",reference,SCHEMA_DIR);validate_schema("generation_runtime_lock",lock,SCHEMA_DIR);slide=next((item for item in package["slides"] if item["slide_id"]==args.slide_id),None)
    if slide is None or reference["deck_id"]!=package["deck_id"] or lock["deck_id"]!=package["deck_id"]:raise ContractError([error("$","Page generation authority mismatch","authority_hash_mismatch")])
    prompt="Use case: productivity-visual\nAsset type: new 16:9 presentation visual layer\nInput image: approved sanitized Style Anchor Reference; use only for palette, density, card language, visual rhythm, and hierarchy. Create a new composition for this slide. Never copy text or specific icons.\n\n"+slide["prompt"]+"\n\nAvoid: "+package["negative_prompt"]
    args.output_dir.mkdir(parents=True,exist_ok=True);prompt_path=args.output_dir/"prompt.txt";manifest_path=args.output_dir/"call_manifest.json"
    if prompt_path.exists() or manifest_path.exists():raise ContractError([error(str(args.output_dir),"generation package exists","overwrite_forbidden")])
    prompt_path.write_text(prompt,encoding="utf-8",newline="\n");manifest={"deck_id":package["deck_id"],"slide_id":slide["slide_id"],"revision":1,"prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),"runtime_lock_sha256":canonical_sha256(lock),"generation_kind":"initial","technical_retry_count":0,"style_anchor_reference_sha256":reference["reference_sha256"]};write_once(manifest_path,manifest);return {"prompt":str(prompt_path),"manifest":str(manifest_path)}
def contact_sheet(args):
    if len(args.preview_record)!=len(args.preview_image):raise ContractError([error("$.previews","record/image count mismatch","preview_set_mismatch")])
    style=load_json(args.style_anchor_record);validate_schema("style_anchor_record",style,SCHEMA_DIR);items=[];images=[]
    for record_path,image_path in zip(args.preview_record,args.preview_image):
        record=load_json(record_path);validate_schema("final_design_preview_record",record,SCHEMA_DIR)
        if sha(image_path)!=record["final_preview_sha256"]:raise ContractError([error(str(image_path),"Preview image hash mismatch","authority_hash_mismatch")])
        items.append({"slide_id":record["slide_id"],"order":int(record["slide_id"].removeprefix("S")),"revision":record["revision"],"final_preview_record_sha256":canonical_sha256(record),"final_preview_sha256":record["final_preview_sha256"]});images.append((record["slide_id"],Image.open(image_path).convert("RGB")))
    items.sort(key=lambda item:item["order"]);by_id={sid:image for sid,image in images};thumb_w,thumb_h=640,360;sheet=Image.new("RGB",(thumb_w,420*len(items)),"#E8ECF3");draw=ImageDraw.Draw(sheet)
    for index,item in enumerate(items):sheet.paste(by_id[item["slide_id"]].resize((thumb_w,thumb_h),Image.Resampling.LANCZOS),(0,index*420));draw.text((20,index*420+370),item["slide_id"],fill="black")
    args.output_image.parent.mkdir(parents=True,exist_ok=True);sheet.save(args.output_image,format="PNG",compress_level=9);manifest={"schema_version":"1.0","artifact_type":"approved_design_preview_manifest","deck_id":style["deck_id"],"style_anchor_sha256":canonical_sha256(style),"previews":items,"status":"ready_for_confirmation"};write_once(args.output_manifest,manifest);record={"schema_version":"1.0","artifact_type":"contact_sheet_record","deck_id":style["deck_id"],"preview_manifest_sha256":canonical_sha256(manifest),"contact_sheet_path":args.output_image.name,"contact_sheet_sha256":sha(args.output_image),"visible_slide_ids":[item["slide_id"] for item in items],"status":"ready"};write_once(args.output_record,record);return {"contact_sheet_sha256":record["contact_sheet_sha256"]}
def approve(args):
    manifest=load_json(args.preview_manifest);feedback=load_json(args.feedback);validate_schema("approved_design_preview_manifest",manifest,SCHEMA_DIR);validate_schema("design_preview_feedback",feedback,SCHEMA_DIR)
    if feedback["decision"]!="accepted" or feedback["change_scope"]!="none" or feedback["affected_slide_ids"] or feedback["preview_manifest_sha256"]!=canonical_sha256(manifest):raise ContractError([error("$.feedback","Deck previews are not explicitly accepted","confirmation_required")])
    result=dict(manifest);result["status"]="approved";write_once(args.output,result);return {"approved_manifest_sha256":canonical_sha256(result)}
def promote(args):
    provisional=load_json(args.provisional_record);preview=load_json(args.final_preview_record);mapping=load_json(args.element_map);validate_schema("provisional_visual_asset_record",provisional,SCHEMA_DIR);validate_schema("final_design_preview_record",preview,SCHEMA_DIR);validate_schema("design_element_map",mapping,SCHEMA_DIR)
    if provisional["generated_layer_sha256"]!=preview["generated_layer_sha256"] or provisional["element_id"] not in {item["element_id"] for item in mapping["elements"]}:raise ContractError([error("$","Provisional asset does not bind approved Preview","authority_hash_mismatch")])
    result={"schema_version":"1.0","artifact_type":"extracted_visual_asset_record","deck_id":preview["deck_id"],"slide_id":preview["slide_id"],"element_id":provisional["element_id"],"visual_ref":provisional["visual_ref"],"approved_preview_sha256":preview["final_preview_sha256"],"generated_layer_sha256":preview["generated_layer_sha256"],"element_map_sha256":canonical_sha256(mapping),"crop_bbox":provisional["crop_bbox"],"output_path":provisional["asset_path"],"output_png_sha256":provisional["asset_sha256"],"background_removal_status":provisional["background_separation"],"extraction_quality":"pass","status":"approved"};validate_schema("extracted_visual_asset_record",result,SCHEMA_DIR);write_once(args.output,result);return {"asset_sha256":result["output_png_sha256"]}
def parser():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest="action",required=True)
    a=s.add_parser("prepare-page-generation");a.add_argument("--prompt-package",type=Path,required=True);a.add_argument("--style-reference-record",type=Path,required=True);a.add_argument("--runtime-lock",type=Path,required=True);a.add_argument("--slide-id",required=True);a.add_argument("--output-dir",type=Path,required=True)
    a=s.add_parser("build-contact-sheet");a.add_argument("--style-anchor-record",type=Path,required=True);a.add_argument("--preview-record",type=Path,action="append",required=True);a.add_argument("--preview-image",type=Path,action="append",required=True);a.add_argument("--output-manifest",type=Path,required=True);a.add_argument("--output-image",type=Path,required=True);a.add_argument("--output-record",type=Path,required=True)
    a=s.add_parser("approve-deck");a.add_argument("--preview-manifest",type=Path,required=True);a.add_argument("--feedback",type=Path,required=True);a.add_argument("--output",type=Path,required=True)
    a=s.add_parser("promote-extracted-asset");a.add_argument("--provisional-record",type=Path,required=True);a.add_argument("--final-preview-record",type=Path,required=True);a.add_argument("--element-map",type=Path,required=True);a.add_argument("--output",type=Path,required=True);return p
def main():
    args=parser().parse_args()
    try:out={"prepare-page-generation":prepare_page,"build-contact-sheet":contact_sheet,"approve-deck":approve,"promote-extracted-asset":promote}[args.action](args);print(json.dumps({"status":"ok",**out},ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({"status":"error","errors":getattr(exc,"errors",[{"path":"$","code":"deck_preview_error","message":str(exc)}])},ensure_ascii=False));return 4
if __name__=="__main__":raise SystemExit(main())
