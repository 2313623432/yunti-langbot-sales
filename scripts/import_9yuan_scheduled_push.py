from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import asyncpg


MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
WPS_CELL_IMAGE_NS = 'http://www.wps.cn/officeDocument/2017/etCustomData'
XDR_NS = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

DEFAULT_PRODUCT_UUID = 'yuanfudao-phonics-course'
DEFAULT_BOT_UUID = '12f70134-3e7e-4b55-8f19-6d3bc3b1f1d4'
DEFAULT_TARGET_TYPE = 'person'
DEFAULT_TARGET_ID = 'ou_26bd1e35ee9080c67ce49964c53ded27'
DEFAULT_PIPELINE_UUID = 'yuanfudao-enhanced-sales-template-pipeline'
DEFAULT_ASSET_DIR = Path('data/scheduled-push/9yuan-english')


def _load_local_env() -> None:
    for env_path in (Path('.env.local'), Path('.env')):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


def _text_of(element: ET.Element) -> str:
    return ''.join(node.text or '' for node in element.iter() if node.tag.endswith('}t'))


def _column_name(cell_ref: str) -> str:
    return ''.join(ch for ch in cell_ref if ch.isalpha())


def _normalize_time(value: str, fallback: str = '10:20') -> str:
    text = (value or '').strip()
    match = re.search(r'(\d{1,2})\s*[:：]\s*(\d{1,2})', text)
    if not match:
        return fallback
    hour = max(0, min(23, int(match.group(1))))
    minute = max(0, min(59, int(match.group(2))))
    return f'{hour:02d}:{minute:02d}'


def _second_message_time(first_time: str) -> str:
    hour, minute = [int(part) for part in first_time.split(':')]
    return '21:20' if (hour, minute) >= (15, 0) else '15:40'


def _parse_shared_strings(zip_file: ZipFile) -> list[str]:
    root = ET.fromstring(zip_file.read('xl/sharedStrings.xml'))
    return [_text_of(si) for si in root.findall(f'{{{MAIN_NS}}}si')]


def _parse_sheet_rows(zip_file: ZipFile, shared_strings: list[str]) -> list[dict[str, str]]:
    sheet = ET.fromstring(zip_file.read('xl/worksheets/sheet1.xml'))
    parsed_rows: list[dict[str, str]] = []
    for row in sheet.findall(f'.//{{{MAIN_NS}}}row'):
        values: dict[str, str] = {}
        for cell in row.findall(f'{{{MAIN_NS}}}c'):
            ref = cell.attrib.get('r', '')
            column = _column_name(ref)
            cell_type = cell.attrib.get('t')
            value_node = cell.find(f'{{{MAIN_NS}}}v')
            inline_node = cell.find(f'{{{MAIN_NS}}}is')
            value = ''
            if cell_type == 's' and value_node is not None:
                value = shared_strings[int(value_node.text or '0')]
            elif cell_type == 'inlineStr' and inline_node is not None:
                value = _text_of(inline_node)
            elif value_node is not None:
                value = value_node.text or ''
            values[column] = value
        parsed_rows.append(values)
    return parsed_rows


def _parse_cell_image_map(zip_file: ZipFile, asset_dir: Path) -> dict[str, str]:
    try:
        image_root = ET.fromstring(zip_file.read('xl/cellimages.xml'))
        rel_root = ET.fromstring(zip_file.read('xl/_rels/cellimages.xml.rels'))
    except KeyError:
        return {}

    relationship_targets = {
        rel.attrib.get('Id', ''): rel.attrib.get('Target', '')
        for rel in rel_root.findall(f'{{{REL_NS}}}Relationship')
    }
    image_map: dict[str, str] = {}
    for cell_image in image_root.findall(f'{{{WPS_CELL_IMAGE_NS}}}cellImage'):
        name_node = cell_image.find(f'.//{{{XDR_NS}}}cNvPr')
        blip_node = cell_image.find(f'.//{{{A_NS}}}blip')
        if name_node is None or blip_node is None:
            continue
        image_id = name_node.attrib.get('name', '')
        embed_id = blip_node.attrib.get(f'{{{R_NS}}}embed', '')
        target = relationship_targets.get(embed_id, '')
        if not image_id or not target or target.upper() == 'NULL':
            continue
        source = 'xl/' + target.lstrip('/')
        suffix = Path(target).suffix or '.png'
        output = asset_dir / f'{image_id}{suffix}'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(zip_file.read(source))
        image_map[image_id] = output.as_posix()
    return image_map


def _extract_image_id(value: str) -> str:
    match = re.search(r'DISPIMG\("([^"]+)"', value or '')
    return match.group(1) if match else ''


def parse_workbook(workbook_path: Path, asset_dir: Path) -> list[dict[str, object]]:
    with ZipFile(workbook_path) as zip_file:
        shared_strings = _parse_shared_strings(zip_file)
        rows = _parse_sheet_rows(zip_file, shared_strings)
        image_map = _parse_cell_image_map(zip_file, asset_dir)

    items: list[dict[str, object]] = []
    for values in rows[1:]:
        day_text = str(values.get('A') or '').strip()
        message = str(values.get('C') or '').strip()
        if not day_text or not message:
            continue
        try:
            day = int(float(day_text))
        except ValueError:
            continue
        first_time = _normalize_time(str(values.get('B') or ''), '10:20')
        image_id = _extract_image_id(str(values.get('D') or ''))
        image_path = image_map.get(image_id, '')
        first_link_marker = str(values.get('E') or '').strip()
        second_message = str(values.get('G') or '').strip()
        second_link_marker = str(values.get('H') or '').strip()
        items.append(
            {
                'day': day,
                'time': first_time,
                'message': message,
                'image_key': image_path,
                'image_note': image_id,
                'link_marker': first_link_marker,
                'source_column': 'C',
            }
        )
        if second_message:
            items.append(
                {
                    'day': day,
                    'time': _second_message_time(first_time),
                    'message': second_message,
                    'image_key': '',
                    'image_note': '',
                    'link_marker': second_link_marker,
                    'source_column': 'G',
                }
            )
    return sorted(items, key=lambda item: (int(item['day']), str(item['time']), str(item['source_column'])))


def _components_for_item(item: dict[str, object], radar_url: str) -> list[dict[str, object]]:
    components: list[dict[str, object]] = [{'type': 'plain', 'text': str(item['message'])}]
    image_key = str(item.get('image_key') or '')
    if image_key:
        components.append({'type': 'image', 'file_key': image_key, 'image_url': ''})
    if str(item.get('link_marker') or '').strip() == '雷达':
        components.append(
            {
                'type': 'link',
                'title': '猿辅导自然拼读9元体验课报名通道',
                'description': '点击进入报名页面，系统会自动记录点击并触发雷达跟进。',
                'url': radar_url,
                'thumb_url': '',
                'include_text_fallback': True,
            }
        )
    return components


def _scheduled_at_for_item(item: dict[str, object], start_date: dt.date) -> dt.datetime:
    day = int(item['day'])
    hour, minute = [int(part) for part in str(item['time']).split(':')]
    return dt.datetime.combine(start_date + dt.timedelta(days=day - 1), dt.time(hour=hour, minute=minute))


def _dedupe_key(*parts: object) -> str:
    raw = '|'.join(str(part) for part in parts)
    return 'excel-9yuan:' + hashlib.md5(raw.encode('utf-8')).hexdigest()


async def replace_scheduled_push_plans(
    items: list[dict[str, object]],
    *,
    database_url: str,
    radar_url: str,
    product_uuid: str,
    bot_uuid: str,
    target_type: str,
    target_id: str,
    start_date: dt.date,
    loop_days: int,
) -> tuple[int, int]:
    conn = await asyncpg.connect(database_url)
    try:
        async with conn.transaction():
            deleted = await conn.fetchval(
                "select count(*) from sales_outreach_plans where segment='course-sales:broadcast'"
            )
            await conn.execute("delete from sales_outreach_plans where segment='course-sales:broadcast'")
            inserted = 0
            interval_minutes = max(0, loop_days) * 24 * 60
            for index, item in enumerate(items, start=1):
                components = _components_for_item(item, radar_url)
                await conn.execute(
                    """
                    insert into sales_outreach_plans (
                        name, product_uuid, bot_uuid, target_type, target_id, segment, dedupe_key,
                        message_template, message_components, scheduled_at, interval_minutes,
                        enabled, last_sent_at, created_at, updated_at
                    ) values (
                        $1, $2, $3, $4, $5, 'course-sales:broadcast', $6,
                        $7, $8::json, $9, $10,
                        true, null, now(), now()
                    )
                    """,
                    f"9元英语课定时推送-D{item['day']}-{item['time']}-{item['source_column']}",
                    product_uuid,
                    bot_uuid,
                    target_type,
                    target_id,
                    _dedupe_key(product_uuid, bot_uuid, target_type, target_id, item['day'], item['time'], index),
                    str(item['message']),
                    json.dumps(components, ensure_ascii=False),
                    _scheduled_at_for_item(item, start_date),
                    interval_minutes,
                )
                inserted += 1
        return int(deleted or 0), inserted
    finally:
        await conn.close()


def _write_preview(items: list[dict[str, object]], preview_path: Path, radar_url: str) -> None:
    preview = []
    for item in items:
        preview.append({**item, 'components': _components_for_item(item, radar_url)})
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Import 9 yuan English course scheduled push workbook.')
    parser.add_argument('--workbook', required=True, help='Path to 9元英语课推广话术表.xlsx')
    parser.add_argument('--radar-url', required=True, help='Real radar URL to replace 雷达 markers.')
    parser.add_argument('--asset-dir', default=str(DEFAULT_ASSET_DIR), help='Where extracted workbook images are stored.')
    parser.add_argument('--preview', default='data/scheduled-push/9yuan-english/preview.json')
    parser.add_argument('--apply', action='store_true', help='Replace current scheduled push plans in PostgreSQL.')
    parser.add_argument('--database-url', default='', help='PostgreSQL URL. Defaults to .env/DATABASE_PUBLIC_URL.')
    parser.add_argument('--product-uuid', default=DEFAULT_PRODUCT_UUID)
    parser.add_argument('--bot-uuid', default=DEFAULT_BOT_UUID)
    parser.add_argument('--target-type', default=DEFAULT_TARGET_TYPE)
    parser.add_argument('--target-id', default=DEFAULT_TARGET_ID)
    parser.add_argument('--pipeline-uuid', default=DEFAULT_PIPELINE_UUID)
    parser.add_argument('--start-date', default=dt.date.today().isoformat())
    args = parser.parse_args()

    _load_local_env()
    workbook_path = Path(args.workbook)
    asset_dir = Path(args.asset_dir)
    items = parse_workbook(workbook_path, asset_dir)
    _write_preview(items, Path(args.preview), args.radar_url)
    loop_days = max((int(item['day']) for item in items), default=0)

    print(f'parsed_items={len(items)}')
    print(f'loop_days={loop_days}')
    print(f'asset_dir={asset_dir.as_posix()}')
    print(f'preview={args.preview}')
    print(f'link_components={sum(1 for item in items if str(item.get("link_marker") or "").strip() == "雷达")}')
    print(f'image_components={sum(1 for item in items if item.get("image_key"))}')

    if not args.apply:
        return

    database_url = args.database_url or os.environ.get('DATABASE_PUBLIC_URL') or os.environ.get('DATABASE_URL') or ''
    if not database_url:
        raise SystemExit('DATABASE_PUBLIC_URL or DATABASE_URL is required when --apply is used.')
    deleted, inserted = asyncio.run(
        replace_scheduled_push_plans(
            items,
            database_url=database_url,
            radar_url=args.radar_url,
            product_uuid=args.product_uuid,
            bot_uuid=args.bot_uuid,
            target_type=args.target_type,
            target_id=args.target_id,
            start_date=dt.date.fromisoformat(args.start_date),
            loop_days=loop_days,
        )
    )
    print(f'deleted_existing_scheduled_push={deleted}')
    print(f'inserted_scheduled_push={inserted}')


if __name__ == '__main__':
    main()
