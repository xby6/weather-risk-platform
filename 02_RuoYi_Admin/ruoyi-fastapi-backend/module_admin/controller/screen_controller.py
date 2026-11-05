from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from module_admin.service.algorithm_task_store import list_tasks
from module_admin.service.notice_read_service import NoticeReadService
from module_admin.service.weather_data_store import list_files

router = APIRouter(prefix='/monitor', tags=['大屏数据'])

CITY_ORDER = [
    '沈阳市',
    '大连市',
    '鞍山市',
    '抚顺市',
    '本溪市',
    '丹东市',
    '锦州市',
    '营口市',
    '阜新市',
    '辽阳市',
    '盘锦市',
    '铁岭市',
    '朝阳市',
    '葫芦岛市',
]
PROVINCE_NAME = '辽宁省'
TABPFN_FORECAST_ALGORITHM_ID = 'tabpfn_fault_forecast'
PREDICTION_SHEET_NAME = '未来故障预测'
PREDICTION_LEVELS = ('低', '一般', '较高', '高')
SCREEN_NOTICE_READER_KEY = 'liaoning-main-screen'
_prediction_file_cache: dict[str, tuple[int, int, list[dict[str, Any]]]] = {}


def _city_keyword(city: str | None) -> str:
    return str(city or '').strip().replace('市', '')


def _match_city(value: Any, city: str | None) -> bool:
    keyword = _city_keyword(city)
    if not keyword:
        return True
    return keyword in str(value or '').replace('市', '')


def _filter_by_city(rows: list[dict[str, Any]], city: str | None, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not _city_keyword(city):
        return rows
    return [row for row in rows if any(_match_city(row.get(key), city) for key in keys)]


def _to_float(value: Any) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_time(value: Any) -> str:
    if hasattr(value, 'strftime'):
        try:
            return value.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    return str(value or '')


def _is_blank(value: Any) -> bool:
    if value in (None, ''):
        return True
    try:
        return bool(value != value)
    except Exception:
        return False


def _task_result_file(task: dict[str, Any]) -> Path | None:
    result = task.get('result') if isinstance(task.get('result'), dict) else {}
    candidates = (task.get('resultPath'), result.get('output_file'))
    for value in candidates:
        if not value:
            continue
        path = Path(str(value)).expanduser()
        try:
            resolved = path.resolve()
        except Exception:
            continue
        if resolved.is_file() and resolved.suffix.lower() in {'.xlsx', '.xls'}:
            return resolved
    return None


def _read_prediction_result_file(path: Path) -> list[dict[str, Any]]:
    stat = path.stat()
    cache_key = str(path)
    cached = _prediction_file_cache.get(cache_key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    import pandas as pd

    frame = pd.read_excel(path, sheet_name=PREDICTION_SHEET_NAME)
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient='records'):
        probability = _to_float(record.get('故障概率'))
        if probability is None:
            percent = _to_float(record.get('故障概率(%)'))
            probability = percent / 100 if percent is not None else None
        level = str(record.get('概率等级') or '').strip()
        if probability is None or not level:
            continue
        city = '' if _is_blank(record.get('运行单位')) else str(record.get('运行单位')).strip()
        line_name = '' if _is_blank(record.get('线路名称')) else str(record.get('线路名称')).strip()
        tower_code = '' if _is_blank(record.get('杆塔编号')) else str(record.get('杆塔编号')).strip()
        forecast_hour = int(_to_float(record.get('预测时效(h)')) or 0)
        rows.append(
            {
                'city': city,
                'region': city,
                'line_name': line_name,
                'line_code': line_name,
                'tower_code': tower_code,
                'name': tower_code or line_name or city or '预测点位',
                'forecast_hour': forecast_hour,
                'forecast_time': _format_time(record.get('预测时间')),
                'start_time': _format_time(record.get('预测起始时间')),
                'probability': probability,
                'probability_percent': round(probability * 100, 3),
                'level': level,
                'predicted_fault': str(record.get('预测是否故障') or '').strip() == '是',
                'temperature': _to_float(record.get('温度')),
                'humidity': _to_float(record.get('湿度')),
                'wind_speed': _to_float(record.get('风速')),
                'precipitation': _to_float(record.get('小时降水')),
                'longitude': _to_float(record.get('经度')),
                'latitude': _to_float(record.get('纬度')),
            }
        )
    _prediction_file_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, rows)
    if len(_prediction_file_cache) > 8:
        oldest_key = next(iter(_prediction_file_cache))
        if oldest_key != cache_key:
            _prediction_file_cache.pop(oldest_key, None)
    return rows


async def _latest_prediction_rows(
    tasks: list[dict[str, Any]], city: str | None = None
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    latest_task = next(
        (
            task
            for task in tasks
            if str(task.get('algorithmId') or '') == TABPFN_FORECAST_ALGORITHM_ID
            and str(task.get('status') or '').lower() == 'success'
            and _task_result_file(task) is not None
        ),
        None,
    )
    if not latest_task:
        return None, []
    path = _task_result_file(latest_task)
    if path is None:
        return latest_task, []
    try:
        rows = await asyncio.to_thread(_read_prediction_result_file, path)
    except Exception:
        return latest_task, []
    return latest_task, _filter_by_city(rows, city, ('region', 'city', 'line_code', 'tower_code', 'name'))


def _prediction_warning_list(task: dict[str, Any] | None, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    task = task or {}
    ordered = sorted(rows, key=lambda row: (-float(row.get('probability') or 0), int(row.get('forecast_hour') or 0)))
    warnings: list[dict[str, Any]] = []
    for row in ordered[:20]:
        longitude = row.get('longitude')
        latitude = row.get('latitude')
        warning = {
            **row,
            'warning_type': task.get('algorithmName') or '杆塔故障概率预测',
            'task_code': task.get('taskCode') or '',
            'task_name': task.get('taskName') or '',
            'time': row.get('forecast_time') or task.get('updateTime') or '',
            'area': row.get('city') or '',
        }
        if longitude is not None and latitude is not None:
            warning['value'] = [longitude, latitude, row.get('probability_percent') or 0]
        warnings.append(warning)
    return warnings


def _prediction_risk_distribution_by_region(rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    present = {str(row.get('city') or '').strip() for row in rows if str(row.get('city') or '').strip()}
    cities = [city for city in CITY_ORDER if any(_match_city(value, city) for value in present)]
    for value in sorted(present):
        if not any(_match_city(value, city) for city in cities):
            cities.append(value)
    counters: dict[str, Counter[str]] = {city: Counter() for city in cities}
    for row in rows:
        region = str(row.get('city') or '')
        city_name = next((item for item in cities if _match_city(region, item)), region)
        if city_name:
            counters.setdefault(city_name, Counter())[str(row.get('level') or '')] += 1
    return {
        'cities': cities,
        'level1': [counters[city]['高'] for city in cities],
        'level2': [counters[city]['较高'] for city in cities],
        'level3': [counters[city]['一般'] for city in cities],
        'level4': [counters[city]['低'] for city in cities],
        'level5': [0 for _ in cities],
    }


def _prediction_hourly_trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        city = str(row.get('city') or '').strip()
        hour = int(row.get('forecast_hour') or 0)
        probability = _to_float(row.get('probability'))
        if city and hour > 0 and probability is not None:
            values[city][hour].append(probability)
    hours = sorted({hour for city_values in values.values() for hour in city_values})
    city_names = [city for city in CITY_ORDER if any(_match_city(value, city) for value in values)]
    for value in sorted(values):
        if not any(_match_city(value, city) for city in city_names):
            city_names.append(value)
    series = []
    for city in city_names:
        source_name = next((value for value in values if _match_city(value, city)), city)
        series.append(
            {
                'name': city,
                'data': [
                    round(sum(values[source_name][hour]) / len(values[source_name][hour]) * 100, 3)
                    if values[source_name].get(hour)
                    else None
                    for hour in hours
                ],
            }
        )
    return {'hours': hours, 'series': series, 'unit': '%'}


def _decode_notice_content(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        for encoding in ('utf-8', 'gbk'):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode('utf-8', errors='ignore')
    return str(value)


async def _list_system_notices(query_db: AsyncSession, limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 10), 50))
    try:
        result = await query_db.execute(
            text(
                f"""
                select notice_id, notice_title, notice_type, notice_content, status,
                       create_by, create_time, update_time, remark
                from sys_notice
                where status = '0'
                order by create_time desc, notice_id desc
                limit {limit}
                """
            )
        )
    except Exception:
        return []

    mappings = result.mappings().all()
    notice_ids = [int(row.get('notice_id')) for row in mappings if row.get('notice_id') is not None]
    read_status = await NoticeReadService.get_read_status_map(
        query_db,
        notice_ids,
        'screen',
        SCREEN_NOTICE_READER_KEY,
    )
    notice_type_map = {'1': '通知', '2': '公告'}
    rows: list[dict[str, Any]] = []
    for row in mappings:
        notice_type = str(row.get('notice_type') or '')
        notice_id = int(row.get('notice_id'))
        rows.append(
            {
                'noticeId': notice_id,
                'noticeTitle': row.get('notice_title') or '',
                'noticeType': notice_type,
                'noticeTypeName': notice_type_map.get(notice_type, notice_type or '公告'),
                'noticeContent': _decode_notice_content(row.get('notice_content')),
                'status': row.get('status') or '',
                'createBy': row.get('create_by') or '',
                'createTime': _format_time(row.get('create_time')),
                'updateTime': _format_time(row.get('update_time')),
                'remark': row.get('remark') or '',
                'isRead': notice_id in read_status,
                'readTime': _format_time(read_status.get(notice_id)),
            }
        )
    return rows


async def _list_weather_observations(query_db: AsyncSession, city: str | None = None) -> list[dict[str, Any]]:
    keyword = _city_keyword(city)
    city_like = f'%{keyword}%' if keyword else ''
    try:
        result = await query_db.execute(
            text(
                """
                select
                    id,
                    region_name,
                    station_code,
                    station_name,
                    line_code,
                    station_or_line,
                    coalesce(observation_time, obs_time, create_time) as weather_time,
                    temperature,
                    humidity,
                    wind_speed,
                    wind_direction,
                    precipitation,
                    pressure,
                    visibility,
                    icing_thickness,
                    history_icing_thickness,
                    longitude,
                    latitude
                from weather_observation
                where (:city_like = ''
                    or region_name like :city_like
                    or station_name like :city_like
                    or station_or_line like :city_like
                    or line_code like :city_like)
                order by coalesce(observation_time, obs_time, create_time) asc, id asc
                limit 500
                """
            ),
            {'city_like': city_like},
        )
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for row in result.mappings().all():
        region = row.get('region_name') or ''
        station = row.get('station_name') or row.get('station_code') or row.get('station_or_line') or row.get('line_code') or region
        rows.append(
            {
                'id': row.get('id'),
                'region': region,
                'city': region,
                'station': station or '',
                'station_or_line': row.get('station_or_line') or '',
                'name': station or region or '',
                'line_code': row.get('line_code') or '',
                'time': _format_time(row.get('weather_time')),
                'temperature': _to_float(row.get('temperature')),
                'humidity': _to_float(row.get('humidity')),
                'wind_speed': _to_float(row.get('wind_speed')),
                'wind_direction': row.get('wind_direction') or '',
                'precipitation': _to_float(row.get('precipitation')),
                'pressure': _to_float(row.get('pressure')),
                'visibility': _to_float(row.get('visibility')),
                'icing_thickness': _to_float(row.get('icing_thickness')),
                'history_icing_thickness': _to_float(row.get('history_icing_thickness')),
                'longitude': _to_float(row.get('longitude')),
                'latitude': _to_float(row.get('latitude')),
            }
        )
    return rows


def _extract_results(task: dict[str, Any]) -> list[dict[str, Any]]:
    raw = task.get('result')
    if isinstance(raw, dict):
        result = raw.get('result')
        if isinstance(result, list):
            return result
    if isinstance(raw, list):
        return raw
    return []


def _warning_from_result(task: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    level = item.get('risk_level') or item.get('warning_level')
    if not level:
        return None
    if str(level) in {'正常', '无风险'}:
        return None
    return {
        'level': level,
        'name': task.get('algorithmName') or task.get('algorithmId') or '算法预警',
        'time': item.get('time') or task.get('updateTime') or task.get('createTime') or '',
        'city': item.get('region') or task.get('region') or '',
        'region': item.get('region') or task.get('region') or '',
        'line_code': item.get('line_code') or task.get('lineCode') or '',
        'warning_type': task.get('taskType') or task.get('algorithmId') or '',
    }


def _latest_weather_params(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    for task in tasks:
        params = task.get('params') or {}
        if any(params.get(k) not in (None, '') for k in ('temperature', 'humidity', 'windSpeed', 'pressure')):
            return params
    return {}


def _screen_task_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'taskCode': task.get('taskCode') or '',
            'taskName': task.get('taskName') or '',
            'algorithmId': task.get('algorithmId') or '',
            'algorithmName': task.get('algorithmName') or '',
            'taskType': task.get('taskType') or '',
            'status': task.get('status') or 'created',
            'progress': int(task.get('progress') or 0),
            'message': task.get('message') or '',
            'region': task.get('region') or '',
            'lineCode': task.get('lineCode') or '',
            'startTime': task.get('startTime') or '',
            'createTime': task.get('createTime') or '',
            'updateTime': task.get('updateTime') or '',
        }
        for task in tasks
    ]


def _latest_weather(weather_rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(weather_rows):
        if any(row.get(key) is not None for key in ('temperature', 'humidity', 'wind_speed', 'precipitation', 'pressure')):
            return row
    return {}


def _weather_trend(weather_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'time': row.get('time') or '',
            'date': str(row.get('time') or '')[:10],
            'region': row.get('region') or '',
            'station': row.get('station') or '',
            'temperature': row.get('temperature'),
            'humidity': row.get('humidity'),
            'wind_speed': row.get('wind_speed'),
            'precipitation': row.get('precipitation'),
        }
        for row in weather_rows[-120:]
    ]


def _station_ranking(weather_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_station: dict[str, dict[str, Any]] = {}
    for row in weather_rows:
        key = row.get('station') or row.get('region') or str(row.get('id') or '')
        latest_by_station[key] = row
    return [
        {
            'name': row.get('station') or row.get('region') or '',
            'region': row.get('region') or '',
            'time': row.get('time') or '',
            'temperature': row.get('temperature'),
            'temp': row.get('temperature'),
            'wind_speed': row.get('wind_speed'),
            'wind': row.get('wind_speed'),
            'precipitation': row.get('precipitation'),
            'rain': row.get('precipitation'),
        }
        for row in latest_by_station.values()
    ]


def _map_points(weather_rows: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    latest_by_region: dict[str, dict[str, Any]] = {}
    for row in weather_rows:
        if row.get('longitude') is None or row.get('latitude') is None:
            continue
        key = row.get('station_or_line') or row.get('station') or row.get('line_code') or str(row.get('id') or '')
        latest_by_region[key] = row
    for row in latest_by_region.values():
        score = row.get('icing_thickness') or row.get('history_icing_thickness') or row.get('precipitation') or 0
        points.append(
            {
                'name': row.get('station_or_line') or row.get('station') or row.get('region') or '气象点',
                'region': row.get('region') or '',
                'time': row.get('time') or '',
                'value': [row.get('longitude'), row.get('latitude'), score],
                'temperature': row.get('temperature'),
                'humidity': row.get('humidity'),
                'wind_speed': row.get('wind_speed'),
                'precipitation': row.get('precipitation'),
            }
        )
    for item in warnings:
        if item.get('longitude') is not None and item.get('latitude') is not None:
            points.append(item)
    return points


def _risk_distribution_by_region(warnings: list[dict[str, Any]]) -> dict[str, list[Any]]:
    city_names = CITY_ORDER.copy()
    if warnings:
        for warning in warnings:
            region = str(warning.get('region') or warning.get('city') or '')
            if region and region not in city_names:
                city_names.append(region)

    counters: dict[str, Counter[str]] = {city: Counter() for city in city_names}
    for warning in warnings:
        region = str(warning.get('region') or warning.get('city') or '')
        matched = next((city for city in city_names if _match_city(region, city)), region or '未知')
        counters.setdefault(matched, Counter())
        counters[matched][_risk_bucket(warning.get('level'))] += 1

    return {
        'cities': city_names,
        'level1': [counters[city]['level1'] for city in city_names],
        'level2': [counters[city]['level2'] for city in city_names],
        'level3': [counters[city]['level3'] for city in city_names],
        'level4': [counters[city]['level4'] for city in city_names],
        'level5': [counters[city]['level5'] for city in city_names],
    }


def _risk_bucket(level: Any) -> str:
    text = str(level or '').upper()
    if '正常' in text or '无' in text:
        return 'level5'
    if 'IV' in text or '蓝' in text or '低' in text:
        return 'level4'
    if 'III' in text or '黄' in text or '中' in text:
        return 'level3'
    if 'II' in text or '橙' in text or '较高' in text:
        return 'level2'
    if 'I' in text or '红' in text or '高' in text:
        return 'level1'
    return 'level3'


@router.get('/screen-all-data', summary='大屏统一数据接口')
async def get_screen_all_data(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    city: str | None = Query(default=None, description='按城市过滤，例如：沈阳市'),
):
    # 大屏只展示真实库表数据；如果业务表尚未建好，返回空数据而不是 500，避免前端白屏。
    try:
        files = await list_files(query_db)
    except Exception:
        files = []
    files = [item for item in files if item.get('itemType') != 'folder' and not item.get('isFolder')]
    try:
        all_tasks = await list_tasks(query_db)
    except Exception:
        all_tasks = []
    weather_rows = await _list_weather_observations(query_db, city)

    files = _filter_by_city(files, city, ('region', 'stationOrLine', 'name', 'fileName'))
    tasks = _filter_by_city(all_tasks, city, ('region', 'lineCode', 'taskName', 'taskCode'))
    finished_files = [i for i in files if i.get('status') in {'finished', 'imported'}]
    params = _latest_weather_params(all_tasks)

    prediction_task, prediction_rows = await _latest_prediction_rows(all_tasks, city)
    prediction_warnings = _prediction_warning_list(prediction_task, prediction_rows)

    warnings: list[dict[str, Any]] = []
    for task in tasks:
        for item in _extract_results(task):
            warning = _warning_from_result(task, item)
            if warning:
                warnings.append(warning)
    warnings = _filter_by_city(warnings, city, ('region', 'city', 'line_code', 'name'))
    warnings = prediction_warnings or warnings[:20]

    level_source = prediction_rows if prediction_rows else warnings
    level_counter = Counter([str(i.get('level') or '未知') for i in level_source])
    risk_distribution = [{'name': k, 'value': v} for k, v in level_counter.items()]

    trend_counter: dict[str, int] = defaultdict(int)
    for item in warnings if not prediction_rows else []:
        raw_time = str(item.get('time') or '')
        date_key = raw_time[:10] if len(raw_time) >= 10 else '未知日期'
        trend_counter[date_key] += 1
    warning_trend = [{'date': k, 'count': v} for k, v in sorted(trend_counter.items())]

    regions = [i.get('region') for i in files if i.get('region')]
    current_region = city or (PROVINCE_NAME if weather_rows or files else '')
    station_or_line = {i.get('stationOrLine') for i in files if i.get('stationOrLine')}
    weather_station_names = {i.get('station') for i in weather_rows if i.get('station')}
    latest_weather = _latest_weather(weather_rows)

    temperature = (
        latest_weather.get('temperature')
        if latest_weather.get('temperature') is not None
        else params.get('temperature') if params.get('temperature') not in (None, '') else None
    )
    humidity = (
        latest_weather.get('humidity')
        if latest_weather.get('humidity') is not None
        else params.get('humidity') if params.get('humidity') not in (None, '') else None
    )
    wind_speed = (
        latest_weather.get('wind_speed')
        if latest_weather.get('wind_speed') is not None
        else params.get('windSpeed') if params.get('windSpeed') not in (None, '') else None
    )
    precipitation = (
        latest_weather.get('precipitation')
        if latest_weather.get('precipitation') is not None
        else params.get('precipitation') if params.get('precipitation') not in (None, '') else None
    )
    pressure = (
        latest_weather.get('pressure')
        if latest_weather.get('pressure') is not None
        else params.get('pressure') if params.get('pressure') not in (None, '') else None
    )

    data = {
        'city': current_region,
        'selected_city': city or '',
        'region_mode': 'city' if _city_keyword(city) else 'province',
        'weather': '',
        'temperature_range': f'{temperature}℃' if temperature is not None else '',
        'station_count': len(station_or_line | weather_station_names),
        'file_count': len(files),
        'finished_file_count': len(finished_files),
        'warning_count': len([row for row in prediction_rows if row.get('predicted_fault')]) if prediction_rows else len(warnings),
        'risk_count': len(risk_distribution),
        'temperature': temperature,
        'humidity': humidity,
        'wind_speed': wind_speed,
        'wind_direction': latest_weather.get('wind_direction') or params.get('windDirection') or '',
        'precipitation': precipitation,
        'pressure': pressure,
        'warning_list': warnings,
        'risk_distribution': risk_distribution,
        'risk_distribution_by_region': _prediction_risk_distribution_by_region(prediction_rows) if prediction_rows else _risk_distribution_by_region(warnings),
        'warning_trend': warning_trend,
        'prediction_hourly_trend': _prediction_hourly_trend(prediction_rows),
        'prediction_count': len(prediction_rows),
        'prediction_task': {
            'taskCode': prediction_task.get('taskCode') or '',
            'taskName': prediction_task.get('taskName') or '',
            'algorithmName': prediction_task.get('algorithmName') or '',
            'updateTime': prediction_task.get('updateTime') or '',
            'usedRealModel': bool(((prediction_task.get('result') or {}).get('summary') or {}).get('used_real_model')),
        } if prediction_task else {},
        'weather_trend': _weather_trend(weather_rows),
        'weather_timeline': weather_rows[-120:],
        'station_ranking': _station_ranking(weather_rows),
        'map_points': _map_points(weather_rows, warnings),
        'task_count': len(tasks),
        'running_task_count': len([t for t in tasks if t.get('status') in {'running', 'queued', 'submitted'}]),
        'success_task_count': len([t for t in tasks if t.get('status') == 'success']),
        'task_list': _screen_task_rows(tasks),
        'weather_files': files[:10],
    }
    return {'code': 200, 'msg': '获取成功', 'data': data}


@router.get('/notices', summary='大屏系统公告列表')
async def get_screen_notices(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    limit: int = Query(default=10, ge=1, le=50),
):
    notices = await _list_system_notices(query_db, limit)
    unread_count = await NoticeReadService.get_unread_count(
        query_db,
        'screen',
        SCREEN_NOTICE_READER_KEY,
    )
    if unread_count < 0:
        unread_count = len([notice for notice in notices if not notice.get('isRead')])
    return {
        'code': 200,
        'msg': '获取成功',
        'data': {'rows': notices, 'total': len(notices), 'unreadCount': unread_count},
    }


@router.post('/notices/{notice_id}/read', summary='大屏阅读系统公告')
async def read_screen_notice(
    notice_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
):
    try:
        read_time = await NoticeReadService.mark_read(
            query_db,
            notice_id,
            'screen',
            SCREEN_NOTICE_READER_KEY,
        )
        unread_count = await NoticeReadService.get_unread_count(
            query_db,
            'screen',
            SCREEN_NOTICE_READER_KEY,
        )
        return {
            'code': 200,
            'msg': '公告已标记为已读',
            'data': {
                'noticeId': notice_id,
                'isRead': True,
                'readTime': _format_time(read_time),
                'unreadCount': max(unread_count, 0),
            },
        }
    except Exception as exc:
        await query_db.rollback()
        return {'code': 500, 'msg': f'公告已读状态保存失败：{exc}', 'data': None}
