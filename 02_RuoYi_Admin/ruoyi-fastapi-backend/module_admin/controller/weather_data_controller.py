from __future__ import annotations

import csv
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Body, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency

from module_admin.service.weather_data_store import (
    UPLOAD_DIR,
    copy_item,
    create_folder,
    delete_file,
    get_file,
    list_files,
    move_item,
    save_file,
    update_file,
)
from module_admin.service.weather_feature_parser import parse_weather_dataset
from utils.response_util import ResponseUtil

router = APIRouter(prefix='/weather-file', tags=['气象数据文件管理'])


def _file_type(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'csv':
        return 'csv'
    if ext in {'xls', 'xlsx'}:
        return 'excel'
    return ext or 'unknown'


def _size_text(size: int) -> str:
    if size >= 1024 * 1024:
        return f'{size / 1024 / 1024:.2f}MB'
    return f'{size / 1024:.1f}KB'


def _detect_data_type(fields: list[str]) -> str:
    joined = ','.join([str(i).lower() for i in fields])
    if 'icing' in joined or '覆冰' in joined or 'ice' in joined:
        return 'icing_monitor'
    if 'grid' in joined or 'lon' in joined and 'lat' in joined:
        return 'grid_forecast'
    if 'line' in joined or '线路' in joined:
        return 'line_weather'
    if 'damage' in joined or 'disaster' in joined or '灾' in joined:
        return 'disaster_history'
    return 'station_observation'


def _parse_csv(path: Path) -> dict[str, Any]:
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            with path.open('r', encoding=enc, newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            if not rows:
                return {'fields': [], 'fieldCount': 0, 'recordCount': 0}
            fields = [str(i).strip() for i in rows[0] if str(i).strip()]
            return {
                'fields': fields,
                'fieldCount': len(fields),
                'recordCount': max(0, len(rows) - 1),
            }
        except UnicodeDecodeError:
            continue
        except Exception:
            break
    return {'fields': [], 'fieldCount': 0, 'recordCount': 0}


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
    except Exception:
        return []
    ns = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    strings = []
    for si in root.findall('a:si', ns):
        parts = [t.text or '' for t in si.findall('.//a:t', ns)]
        strings.append(''.join(parts))
    return strings


def _cell_text(cell, shared: list[str], ns: dict[str, str]) -> str:
    t = cell.attrib.get('t')
    v = cell.find('a:v', ns)
    if v is None or v.text is None:
        return ''
    if t == 's':
        try:
            return shared[int(v.text)]
        except Exception:
            return ''
    return v.text


def _parse_xlsx(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as zf:
            sheet_names = [n for n in zf.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
            if not sheet_names:
                return {'fields': [], 'fieldCount': 0, 'recordCount': 0}
            shared = _xlsx_shared_strings(zf)
            root = ET.fromstring(zf.read(sheet_names[0]))
            ns = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows = root.findall('.//a:sheetData/a:row', ns)
            fields: list[str] = []
            if rows:
                for c in rows[0].findall('a:c', ns):
                    value = _cell_text(c, shared, ns).strip()
                    if value:
                        fields.append(value)
            return {'fields': fields, 'fieldCount': len(fields), 'recordCount': max(0, len(rows) - 1)}
    except Exception:
        return {'fields': [], 'fieldCount': 0, 'recordCount': 0}


def _parse_file(path: Path, file_type: str) -> dict[str, Any]:
    if file_type == 'csv' or path.suffix.lower() == '.xlsx':
        try:
            parsed = parse_weather_dataset(path, include_samples=False)
            return {
                'fields': parsed.get('fields') or [],
                'fieldCount': parsed.get('field_count') or 0,
                'recordCount': parsed.get('record_count') or 0,
            }
        except Exception:
            pass
    if file_type == 'csv':
        return _parse_csv(path)
    if path.suffix.lower() == '.xlsx':
        return _parse_xlsx(path)
    return {'fields': [], 'fieldCount': 0, 'recordCount': 0}


@router.get('/list', summary='获取气象数据文件列表')
async def weather_file_list(query_db: Annotated[AsyncSession, DBSessionDependency()]):
    rows = await list_files(query_db)
    return ResponseUtil.success(data={'rows': rows, 'total': len(rows)}, msg='气象数据文件列表获取成功')


@router.post('/create', summary='手动登记气象数据文件')
async def weather_file_create(query_db: Annotated[AsyncSession, DBSessionDependency()], payload: dict[str, Any] = Body(...)):
    row = {
        'name': payload.get('name') or '',
        'itemType': payload.get('itemType') or 'file',
        'parentId': int(payload.get('parentId') or payload.get('parent_id') or 0),
        'dataType': payload.get('dataType') or 'station_observation',
        'fileType': payload.get('fileType') or 'excel',
        'region': payload.get('region') or '',
        'stationOrLine': payload.get('stationOrLine') or '',
        'timeResolution': payload.get('timeResolution') or '',
        'startTime': payload.get('startTime') or '',
        'endTime': payload.get('endTime') or '',
        'recordCount': int(payload.get('recordCount') or 0),
        'fieldCount': int(payload.get('fieldCount') or 0),
        'fields': payload.get('fields') or '',
        'size': payload.get('size') or '',
        'filePath': payload.get('filePath') or '',
        'status': payload.get('status') or 'pending',
        'progress': int(payload.get('progress') or 0),
        'remark': payload.get('remark') or '',
    }
    try:
        return ResponseUtil.success(data=await save_file(query_db, row), msg='气象数据文件已登记')
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))


@router.post('/folder/create', summary='新建气象数据文件夹')
async def weather_folder_create(query_db: Annotated[AsyncSession, DBSessionDependency()], payload: dict[str, Any] = Body(...)):
    try:
        row = await create_folder(
            query_db,
            name=payload.get('name') or payload.get('folderName') or '',
            parent_id=payload.get('parentId') or payload.get('parent_id') or 0,
            remark=payload.get('remark') or '',
        )
        return ResponseUtil.success(data=row, msg='文件夹已创建')
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))


@router.post('/upload', summary='上传 Excel/CSV 气象数据文件')
async def weather_file_upload(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    file: UploadFile = File(...),
    parent_id: int = Form(0),
):
    if parent_id:
        parent = await get_file(query_db, parent_id)
        if not parent or parent.get('itemType') != 'folder':
            return ResponseUtil.failure(msg='父级文件夹不存在')
    filename = file.filename or f'weather_{datetime.now().strftime("%Y%m%d%H%M%S")}'
    safe_name = filename.replace('/', '_').replace('\\', '_')
    target = UPLOAD_DIR / f'{datetime.now().strftime("%Y%m%d%H%M%S_%f")}_{safe_name}'
    with target.open('wb') as f:
        shutil.copyfileobj(file.file, f)
    size = target.stat().st_size
    ftype = _file_type(filename)
    parsed = _parse_file(target, ftype)
    fields = parsed.get('fields') or []
    row = {
        'name': filename,
        'parentId': parent_id,
        'dataType': _detect_data_type(fields),
        'fileType': ftype,
        'region': '',
        'stationOrLine': '',
        'timeResolution': '',
        'startTime': '',
        'endTime': '',
        'recordCount': parsed.get('recordCount') or 0,
        'fieldCount': parsed.get('fieldCount') or 0,
        'fields': ', '.join(fields),
        'size': _size_text(size),
        'filePath': str(target).replace('\\', '/'),
        'status': 'pending',
        'progress': 0,
        'remark': '已上传真实文件，待补充区域、站点/线路和时间范围后解析入库。',
    }
    return ResponseUtil.success(data=await save_file(query_db, row), msg='文件上传成功')


@router.post('/move', summary='移动气象数据文件或文件夹')
async def weather_file_move(query_db: Annotated[AsyncSession, DBSessionDependency()], payload: dict[str, Any] = Body(...)):
    try:
        row = await move_item(
            query_db,
            item_id=payload.get('id') or payload.get('fileId') or payload.get('itemId'),
            target_parent_id=payload.get('targetParentId') or payload.get('parentId') or 0,
        )
        if not row:
            return ResponseUtil.failure(msg='气象数据文件不存在')
        return ResponseUtil.success(data=row, msg='移动成功')
    except (TypeError, ValueError) as exc:
        return ResponseUtil.failure(msg=str(exc))


@router.post('/copy', summary='复制气象数据文件或文件夹')
async def weather_file_copy(query_db: Annotated[AsyncSession, DBSessionDependency()], payload: dict[str, Any] = Body(...)):
    try:
        row = await copy_item(
            query_db,
            item_id=payload.get('id') or payload.get('fileId') or payload.get('itemId'),
            target_parent_id=payload.get('targetParentId') or payload.get('parentId') or 0,
        )
        return ResponseUtil.success(data=row, msg='复制成功')
    except (TypeError, ValueError) as exc:
        return ResponseUtil.failure(msg=str(exc))


@router.post('/process/{file_id}', summary='标记气象数据文件已解析入库')
async def weather_file_process(file_id: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    row = await get_file(query_db, file_id)
    if not row:
        return ResponseUtil.failure(msg='气象数据文件不存在')
    row = await update_file(query_db, file_id, status='finished')
    return ResponseUtil.success(data=row, msg='解析入库状态已更新')


@router.delete('/{file_id}', summary='删除气象数据文件记录')
async def weather_file_delete(file_id: str, query_db: Annotated[AsyncSession, DBSessionDependency()]):
    ok = await delete_file(query_db, file_id)
    if ok:
        return ResponseUtil.success(msg='气象数据文件已删除')
    return ResponseUtil.failure(msg='气象数据文件不存在')
