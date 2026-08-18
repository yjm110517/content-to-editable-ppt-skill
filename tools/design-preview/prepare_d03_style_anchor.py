from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/"content-to-editable-ppt"/"scripts";P1=ROOT/"tools"/"content-planning";P2=ROOT/"tools"/"wireframe";sys.path[:0]=[str(SCRIPTS),str(P1),str(P2)]
from canonical_artifact import canonical_sha256
from p1_content_planning_eval import load_fixtures
from visual_system_authority import freeze_visual_system,load_visual_system_authority
from visual_system_prompt import compile_prompt_package,compile_text_footprints
from style_anchor_workflow import prepare
def load_module(path:Path):spec=importlib.util.spec_from_file_location("p32_eval",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
P32=load_module(ROOT/"tools"/"visual-system"/"p3_2_visual_system_eval.py")
def write(path:Path,value:dict):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
    p=argparse.ArgumentParser();p.add_argument("--work-root",type=Path,required=True);args=p.parse_args();root=args.work_root.resolve();root.mkdir(parents=True,exist_ok=True);fixtures=load_fixtures();case=next(item for item in fixtures["cases"] if item["case_id"]=="D03");config=P32.load(P32.P2_CONFIG);timestamp=config["fixed_timestamp_utc"];_,paths=P32.prepare(case,config["cases"]["D03"],timestamp,root/"authority");bundle=load_visual_system_authority(p1_state_path=paths["p1_state"],deck_request_path=paths["request"],approved_outline_path=paths["outline"],slide_content_dir=paths["content"],p2_state_path=paths["p2_state"],wireframe_root=paths["wireframes"],icon_asset_index_path=paths["index"]);candidate=P32.system_candidate(bundle,"D03",timestamp,"educational editorial");system=freeze_visual_system(candidate,bundle);foot=compile_text_footprints(system,bundle);package,anchor=compile_prompt_package(system,foot,bundle)
    write(root/"deck-visual-system.json",system);write(root/"text-footprint-manifest.json",foot);write(root/"deck-prompt-package.json",package);write(root/"style-anchor-request.json",anchor);lock={"schema_version":"1.0","artifact_type":"generation_runtime_lock","deck_id":"D03","backend":"image_gen.imagegen","provider_policy":"runtime_default","model_policy":"runtime_default","model_identity_status":"not_exposed","model_id":None,"model_version":None,"runtime_fingerprint":canonical_sha256({"backend":"image_gen.imagegen","policy":"runtime_default","scope":"p3.3-d03"}),"runtime_scope_id":"p3.3-d03-live-001","status":"locked"};write(root/"generation-runtime-lock.json",lock);prepare(argparse.Namespace(prompt_package=root/"deck-prompt-package.json",anchor_request=root/"style-anchor-request.json",runtime_lock=root/"generation-runtime-lock.json",output_dir=root/"generation-package"));print(json.dumps({"status":"ready","slide_id":anchor["slide_id"],"prompt":str(root/"generation-package"/"prompt.txt"),"work_root":str(root)},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
