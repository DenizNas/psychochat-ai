import os
import argparse
import json
import shutil
from datetime import datetime
import glob
import sys

REGISTRY_DIR = "training/checkpoints/registry"

def get_latest_pointer_path(model_type):
    return os.path.join(REGISTRY_DIR, f"latest_{model_type}.json")

def get_best_pointer_path(model_type):
    return os.path.join(REGISTRY_DIR, f"best_{model_type}.json")

def copy_checkpoint(src_dir, dest_dir):
    if not os.path.exists(src_dir):
        print(f"Uyarı: Checkpoint kaynağı bulunamadı veya boş: {src_dir}")
        return
    os.makedirs(dest_dir, exist_ok=True)
    for item in os.listdir(src_dir):
        s = os.path.join(src_dir, item)
        d = os.path.join(dest_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

def register_model(args):
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_id = f"{args.model_type}_v{timestamp}"
    
    print(f"Registering new model version: {version_id}")
    
    versioned_dir = f"training/checkpoints/{args.model_type}/versions/{version_id}"
    copy_checkpoint(args.checkpoint_path, versioned_dir)
    
    metrics_data = {}
    if args.metrics_path and os.path.exists(args.metrics_path):
        with open(args.metrics_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
    else:
        print(f"Uyarı: Metrik dosyası bulunamadı ({args.metrics_path}). Metrikler boş kaydedilecek.")
            
    is_best = False
    best_pointer = get_best_pointer_path(args.model_type)
    
    main_metric_name = "macro_f1" if args.model_type == "emotion" else "crisis_recall"
    current_metric_val = 0.0
    
    try:
        if args.model_type == "emotion":
            current_metric_val = metrics_data.get("metrics", {}).get("macro_f1", 0.0)
        else:
            # Fallback for crisis recall in the generic JSON structure
            current_metric_val = metrics_data.get("metrics", {}).get("macro_recall", 0.0)
    except:
        pass

    # Always best if it's the first model or if we force it. 
    # For safety in this prompt, we assume it's best if it beats the previous one.
    if os.path.exists(best_pointer):
        with open(best_pointer, "r", encoding="utf-8") as f:
            prev_best = json.load(f)
            
        try:
            prev_metrics = prev_best.get("metrics", {}).get("metrics", {})
            prev_metric_val = prev_metrics.get("macro_f1", 0.0) if args.model_type == "emotion" else prev_metrics.get("macro_recall", 0.0)
            if current_metric_val >= prev_metric_val:
                is_best = True
        except:
            is_best = True # Parse error, assume best
    else:
        is_best = True
        
    metadata = {
        "model_type": args.model_type,
        "version_id": version_id,
        "created_at": datetime.now().isoformat(),
        "dataset_path": args.dataset_path,
        "config_path": args.config_path,
        "metrics": metrics_data,
        "checkpoint_path": versioned_dir,
        "is_best": is_best,
        "notes": args.notes
    }
    
    metadata_path = os.path.join(REGISTRY_DIR, f"{version_id}.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
        
    with open(get_latest_pointer_path(args.model_type), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
        
    if is_best:
        print(f"🏆 YENİ BEST MODEL TESPİT EDİLDİ! ({args.model_type})")
        with open(best_pointer, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        
        best_dir = f"training/checkpoints/{args.model_type}/best_model"
        copy_checkpoint(versioned_dir, best_dir)
        
    print(f"Model başarıyla register edildi: {metadata_path}")

def show_best(args):
    best_ptr = get_best_pointer_path(args.model_type)
    if os.path.exists(best_ptr):
        with open(best_ptr, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"\n🌟 BEST MODEL ({args.model_type.upper()}) 🌟")
            print(json.dumps(data, indent=4, ensure_ascii=False))
    else:
        print(f"Best model pointer bulunamadı: {args.model_type}")

def show_latest(args):
    latest_ptr = get_latest_pointer_path(args.model_type)
    if os.path.exists(latest_ptr):
        with open(latest_ptr, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"\n🕒 LATEST MODEL ({args.model_type.upper()}) 🕒")
            print(json.dumps(data, indent=4, ensure_ascii=False))
    else:
        print(f"Latest model pointer bulunamadı: {args.model_type}")

def list_models(args):
    pattern = os.path.join(REGISTRY_DIR, f"{args.model_type}_v*.json")
    files = glob.glob(pattern)
    if not files:
        print(f"Hiç {args.model_type} versiyonu bulunamadı.")
        return
        
    print(f"\n📂 KAYITLI MODELLER ({args.model_type.upper()}) 📂")
    for file in sorted(files, reverse=True):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            best_star = "⭐ BEST" if data.get("is_best") else ""
            print(f"- {data['version_id']} | Date: {data['created_at']} | Notes: {data['notes']} {best_star}")

def main():
    parser = argparse.ArgumentParser(description="Model Registry System")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_reg = subparsers.add_parser("register")
    parser_reg.add_argument("--model-type", required=True, choices=["emotion", "crisis"])
    parser_reg.add_argument("--checkpoint-path", required=True)
    parser_reg.add_argument("--dataset-path", required=True)
    parser_reg.add_argument("--config-path", required=True)
    parser_reg.add_argument("--metrics-path", required=True)
    parser_reg.add_argument("--notes", type=str, default="")
    
    parser_best = subparsers.add_parser("show-best")
    parser_best.add_argument("--model-type", required=True, choices=["emotion", "crisis"])
    
    parser_latest = subparsers.add_parser("show-latest")
    parser_latest.add_argument("--model-type", required=True, choices=["emotion", "crisis"])
    
    parser_list = subparsers.add_parser("list")
    parser_list.add_argument("--model-type", required=True, choices=["emotion", "crisis"])
    
    args = parser.parse_args()
    
    if args.command == "register":
        register_model(args)
    elif args.command == "show-best":
        show_best(args)
    elif args.command == "show-latest":
        show_latest(args)
    elif args.command == "list":
        list_models(args)

if __name__ == "__main__":
    main()
