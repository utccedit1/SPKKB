"""Local JSON CLI for event editing, callable by Codex shell tools."""
import argparse
import json
import sys
from ks import event_clip


def main():
    parser = argparse.ArgumentParser(description='วิเคราะห์ซับและตัด Event บนไทม์ไลน์เดิมพร้อม backup')
    parser.add_argument('action', choices=['transcript', 'analyze', 'plan', 'apply', 'restore', 'backups'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--config', help='JSON config file; apply accepts saved plan JSON')
    parser.add_argument('--output', help='Save JSON result to this file')
    args = parser.parse_args()
    try:
        cfg = {}
        if args.config:
            with open(args.config, encoding='utf-8') as f:
                cfg = json.load(f)
        if args.action == 'transcript':
            _, rows, digest = event_clip.transcript(args.project, cfg.get('speaker_ranges'))
            result = {'ok': True, 'captions': rows, 'source_hash': digest}
        else:
            result = event_clip.dispatch(args.action, args.project, cfg)
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(text)
        print(text)
        return 0 if result.get('ok') else 1
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
