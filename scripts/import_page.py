#!/usr/bin/env python3
"""Import an untouched Sorftime MCP traffic response into a local page record."""
import argparse
import json
from pathlib import Path
from quality import import_page, write

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--page',type=int,required=True)
    args=parser.parse_args()
    try:
        envelope=json.loads(args.input.read_text(encoding='utf-8'))
        page=import_page(envelope,args.page)
        if args.output.exists():
            old=json.loads(args.output.read_text(encoding='utf-8'))
            if old != page: raise ValueError('refusing to overwrite a different saved page')
        else:
            write(args.output.parent,args.output.name,page)
        print(json.dumps({'page':args.page,'records':len(page['records']),'empty':not page['records']}))
        return 0
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:
        print('ERROR: '+str(error))
        return 1

if __name__=='__main__': raise SystemExit(main())
