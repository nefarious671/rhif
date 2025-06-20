import argparse
from pathlib import Path

import ijson
import requests
from tqdm import tqdm


def stream_messages(path):
    with open(path, 'rb') as f:
        parser = ijson.parse(f)
        conv_id = None
        for prefix, event, value in parser:
            if (prefix, event) == ('conversation_id', 'string'):
                conv_id = value
            if prefix.endswith('.message.content') and event == 'string':
                yield conv_id, value


def ingest_message(hub, data):
    for _ in range(3):
        res = requests.post(f'{hub}/ingest', json=data)
        if res.status_code == 429:
            continue
        res.raise_for_status()
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--export-dir', required=True)
    ap.add_argument('--hub', default='http://127.0.0.1:8765')
    ap.add_argument('--max-per-conv', type=int, default=1000)
    ap.add_argument('--summariser', choices=['ollama', 'gemini'], default='ollama')
    args = ap.parse_args()

    conv_path = Path(args.export_dir) / 'conversations.json'
    total = 0
    with open(conv_path, 'r') as f:
        objects = ijson.items(f, 'conversations.item')
        for conv in tqdm(objects, desc='conversations'):
            conv_id = conv.get('id')
            turn = 1
            for m in conv.get('mapping', {}).values():
                content = m.get('message', {}).get('content', {})
                if content.get('content_type') != 'text':
                    continue
                for part in content.get('parts', []):
                    if len(part) > 8000:
                        continue
                    data = {
                        'conv_id': conv_id,
                        'turn': turn,
                        'role': m.get('message', {}).get('author', {}).get('role', 'assistant'),
                        'date': m.get('message', {}).get('create_time', '')[:10],
                        'text': part,
                        'tags': ['#legacy'],
                    }
                    ingest_message(args.hub, data)
                    turn += 1
                    total += 1
                    if turn > args.max_per_conv:
                        break
    print('Packets ingested:', total)


if __name__ == '__main__':
    main()
