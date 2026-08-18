from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from canonical_artifact import canonical_sha256
from schema_utils import ContractError,error,load_json,validate_schema
SCHEMA_DIR=Path(__file__).resolve().parents[1]/"schemas"
def file_sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--deck-id",required=True);p.add_argument("--slide-id",required=True);p.add_argument("--element-map",type=Path,required=True);p.add_argument("--compatibility-report",type=Path,required=True);p.add_argument("--layout",type=Path,required=True);p.add_argument("--asset-manifest",type=Path,required=True);p.add_argument("--preview-pptx",type=Path,required=True);p.add_argument("--output",type=Path,required=True);args=p.parse_args()
    try:
        if args.output.exists():raise ContractError([error("$.output","output exists","overwrite_forbidden")])
        mapping=load_json(args.element_map);compat=load_json(args.compatibility_report);validate_schema("design_element_map",mapping,SCHEMA_DIR);validate_schema("reconstruction_compatibility_report",compat,SCHEMA_DIR)
        if compat["status"]!="pass" or compat["element_map_sha256"]!=canonical_sha256(mapping):raise ContractError([error("$.compatibility_report","Preview build requires passing current compatibility evidence","reconstruction_incompatible")])
        result={"schema_version":"1.0","artifact_type":"preview_powerpoint_build_report","deck_id":args.deck_id,"slide_id":args.slide_id,"element_map_sha256":canonical_sha256(mapping),"compatibility_report_sha256":canonical_sha256(compat),"layout_sha256":file_sha(args.layout),"asset_manifest_sha256":file_sha(args.asset_manifest),"preview_pptx_sha256":file_sha(args.preview_pptx),"preview_only":True,"delivery_forbidden":True,"powerpoint_render_required":True,"status":"built"};validate_schema("preview_powerpoint_build_report",result,SCHEMA_DIR);args.output.parent.mkdir(parents=True,exist_ok=True);tmp=args.output.with_suffix(args.output.suffix+".tmp");tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(tmp,args.output);print(json.dumps({"status":"ok","report":str(args.output)},ensure_ascii=False));return 0
    except Exception as exc:
        errors=exc.errors if isinstance(exc,ContractError) else [{"path":"$","code":"preview_build_error","message":str(exc)}];print(json.dumps({"status":"error","errors":errors},ensure_ascii=False));return 4
if __name__=="__main__":raise SystemExit(main())
