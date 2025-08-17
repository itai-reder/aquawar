import pickle
import json
import os
import argparse

def unpack_pkl(select_files=['latest.pkl'], save_dir=""):
    for file in select_files:
        with open(os.path.join(save_dir, file), "rb") as f:
            state = pickle.load(f)
            print(f"=== Loaded state from {file}: ===")
            print(f"Keys:")
            for k, v in state.items():
                if type(v) is dict:
                    print(f"  {k}: {[f'{kk}: {type(vv).__name__}' for kk, vv in v.items()]} | {len(v)} items")
                elif type(v) is list and len(v) > 0 and type(v[-1]) is dict:
                    print(f"  {k}: list({[f'{kk}: {type(vv).__name__}' for kk, vv in v[-1].items()]}) | {len(v)} items")
            print(json.dumps(state, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Unpack and examine pickle files")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--files", nargs="+", default=None, help="List of pickle files to unpack")
    group.add_argument("--all", action="store_true", help="Unpack all .pkl files in the directory")
    parser.add_argument("--dir", default="", help="Directory containing the pickle files")
    args = parser.parse_args()

    if args.all:
        if not args.dir:
            parser.error("--all requires --dir to be specified")
        select_files = [f for f in os.listdir(args.dir) if f.endswith('.pkl')]
        if not select_files:
            parser.error(f"No .pkl files found in directory {args.dir}")
    else:
        select_files = args.files if args.files is not None else ['latest.pkl']

    unpack_pkl(select_files=select_files, save_dir=args.dir)

if __name__ == "__main__":
    main()
