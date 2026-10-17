import argparse,json
from pathlib import Path
from .contract import load_packet,validate_packet,compare_event,ContractError
from .adapters import export_reference

def main():
    parser=argparse.ArgumentParser(description='DMS v0.1 export, validation, and event comparison')
    commands=parser.add_subparsers(dest='command',required=True)
    exp=commands.add_parser('export-reference');exp.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1]);exp.add_argument('--out',type=Path,required=True)
    val=commands.add_parser('validate');val.add_argument('packet',type=Path)
    comp=commands.add_parser('compare');comp.add_argument('left',type=Path);comp.add_argument('right',type=Path);comp.add_argument('--event',required=True)
    args=parser.parse_args()
    try:
        if args.command=='export-reference':
            paths=export_reference(args.project,args.out);print(json.dumps({'exported':len(paths),'mapping_validated':False,'out':str(args.out)}))
        elif args.command=='validate':print(json.dumps(validate_packet(*load_packet(args.packet))))
        else:print(json.dumps(compare_event(load_packet(args.left),load_packet(args.right),event_name=args.event)))
    except (ContractError,ValueError,KeyError,TypeError,OSError) as exc:
        if args.command=='compare':print(json.dumps({'comparable':False,'reason':f'Invalid packet: {exc}'}))
        else:parser.exit(2,f'Invalid packet: {exc}\n')

if __name__=='__main__':main()
