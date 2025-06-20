import argparse
from pathlib import Path

import ijson
import requests
from tqdm import tqdm


def ingest_message(hub, data):
    for _ in range(3):
        res = requests.post(f'{hub}/ingest', json=data)
        if res.status_code == 429:
            continue
        res.raise_for_status()
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--export-dir', required=True, help="Directory containing conversations.json")
    ap.add_argument('--hub', default='http://127.0.0.1:8765', help="URL of the ingestion hub")
    ap.add_argument('--max-per-conv', type=int, default=100000, help="Max messages per conversation to ingest")
    ap.add_argument('--summariser', choices=['ollama', 'gemini'], default='ollama', help="Summariser to use")
    args = ap.parse_args()

    conv_path = Path(args.export_dir) / 'conversations.json'
    total = 0
    with open(conv_path, 'r', encoding='utf-8') as f:
        # Top-level JSON is an array, so parse using 'item'
        conversations = ijson.items(f, 'item')
        for conv in tqdm(conversations, desc='Conversations'):
            conv_id = conv.get('id', conv.get('title', 'unknown-conv-id'))
            turn = 1
            mapping = conv.get('mapping', {})

            # Messages might be out of order, so sort or iterate carefully
            # We'll just iterate over mapping.values() and ingest text messages
            for msg_id, msg_node in mapping.items():
                message = msg_node.get('message')
                if not message:
                    continue

                role = message.get('author', {}).get('role', '') or 'assistant'
                if role in ('system', 'tool'):
                    continue

                content = message.get('content', {})
                if content.get('content_type') != 'text':
                    continue

                raw_parts = content.get('parts', [])
                parts = [p for p in raw_parts if p and p.strip()]
                if not parts:
                    continue

                for part in parts:
                    if len(part) > 8000:
                        continue
                    data = {
                        'conv_id': conv_id,
                        'turn': turn,
                        'role': role,
                        'date': (str(message.get('create_time'))[:10]
                                 if message.get('create_time') else ''),
                        'text': part,
                        'tags': ['#legacy'],
                    }
                    try:
                        ingest_message(args.hub, data)
                    except Exception as e:
                        print(f"Failed to ingest turn {turn} of {conv_id}: {e}")
                    turn += 1
                    total += 1
                    if turn > args.max_per_conv:
                        break

    print(f'Packets ingested: {total}')


if __name__ == '__main__':
    main()
