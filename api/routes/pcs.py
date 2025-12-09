"""
API маршруты для работы с ПК
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
import csv
import io

from infrastructure.database.session import get_db
from infrastructure.database.models import User, PC, PCConfiguration
from infrastructure.database.repositories.pc_repository import PCRepository
from infrastructure.database.repositories.config_repository import ConfigRepository
from infrastructure.database.repositories.current_config_repository import CurrentConfigRepository
from api.dependencies import get_current_user
from api.schemas.pc import PCListResponse, PCDetailResponse, SetBaselineResponse
from api.schemas.location import UpdateLocationRequest, BulkUpdateLocationRequest, BulkUpdateLocationResponse
from common.location_parser import update_pc_location
from core.services.comparison_service import ComparisonService

router = APIRouter(prefix="/api/pcs", tags=["PCs"])


def get_pc_repository(db: Session = Depends(get_db)) -> PCRepository:
    """Dependency для получения репозитория ПК"""
    return PCRepository(db)


def get_config_repository(db: Session = Depends(get_db)) -> ConfigRepository:
    """Dependency для получения репозитория конфигураций"""
    return ConfigRepository(db)


def get_current_config_repository(db: Session = Depends(get_db)) -> CurrentConfigRepository:
    """Dependency для получения репозитория текущих конфигураций"""
    return CurrentConfigRepository(db)


@router.get("", response_model=PCListResponse)
async def get_pcs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    building: Optional[str] = None,
    floor: Optional[str] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = 'asc',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository),
    config_repo: ConfigRepository = Depends(get_config_repository),
    current_config_repo: CurrentConfigRepository = Depends(get_current_config_repository)
):
    """Получить список ПК с фильтрацией и сортировкой"""
    # Обновляем статус offline перед получением списка
    pc_repo.update_offline_status(offline_threshold_minutes=10)
    
    # Нормализуем все поисковые поля (приводим к нижнему регистру для регистронезависимого поиска)
    normalized_building = building.lower().strip() if building else None
    normalized_floor = floor.lower().strip() if floor else None
    normalized_location = location.lower().strip() if location else None
    normalized_search = search.lower().strip() if search else None
    
    pcs = pc_repo.find_all(
        skip=skip, 
        limit=limit, 
        status=status,
        building=normalized_building,
        floor=normalized_floor,
        location=normalized_location,
        search=normalized_search,
        sort_by=sort_by,
        sort_order=sort_order
    )
    total = pc_repo.count_all(
        status=status,
        building=normalized_building,
        floor=normalized_floor,
        location=normalized_location,
        search=normalized_search
    )
    
    # Оптимизация: используем таблицу текущего состояния для быстрого доступа
    pc_ids = [pc.pc_id for pc in pcs]
    
    if not pc_ids:
        return PCListResponse(total=0, items=[])
    
    # Загружаем все текущие конфигурации одним запросом (быстро!)
    current_configs = current_config_repo.find_all(pc_ids)
    current_configs_dict = {config.pc_id: config for config in current_configs}
    
    # Обогащаем данные ПК информацией из текущего состояния (IP и версия агента)
    items = []
    for pc in pcs:
        pc_dict = pc.to_dict()
        
        # Получаем текущее состояние конфигурации
        current_config = current_configs_dict.get(pc.pc_id)
        
        if current_config:
            # Версия агента
            pc_dict['agent_version'] = current_config.agent_version
            
            # IP-адреса из network_adapters
            ip_addresses = []
            if current_config.network_adapters:
                try:
                    network_data = current_config.get_component('network_adapters')
                    if network_data and isinstance(network_data, list):
                        for adapter in network_data:
                            if isinstance(adapter, dict):
                                adapter_ips = adapter.get('ip_addresses', [])
                                if adapter_ips:
                                    # Фильтруем только IPv4 адреса (без IPv6)
                                    for ip in adapter_ips:
                                        if ':' not in ip:  # IPv4 не содержит двоеточий
                                            ip_addresses.append(ip)
                except Exception as e:
                    # Логируем ошибку для отладки
                    import logging
                    logging.getLogger(__name__).warning(f"Error parsing network_adapters for {pc.pc_id}: {e}", exc_info=True)
            
            # Берем первый IPv4 адрес или все, если их немного
            if ip_addresses:
                # Убираем дубликаты и берем до 3 адресов
                unique_ips = list(dict.fromkeys(ip_addresses))[:3]
                pc_dict['ip_addresses'] = unique_ips
                pc_dict['ip_address'] = unique_ips[0]  # Основной IP для отображения
            else:
                pc_dict['ip_addresses'] = []
                pc_dict['ip_address'] = None
        else:
            # Нет текущего состояния
            pc_dict['agent_version'] = None
            pc_dict['ip_addresses'] = []
            pc_dict['ip_address'] = None
        
        items.append(pc_dict)
    
    return PCListResponse(
        total=total,
        items=items
    )


@router.get("/{pc_id}/history")
async def get_pc_history(
    pc_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository),
    config_repo: ConfigRepository = Depends(get_config_repository),
    current_config_repo: CurrentConfigRepository = Depends(get_current_config_repository)
):
    """
    Получить историю изменений конфигурации ПК
    
    Возвращает:
    - Эталонную конфигурацию (baseline)
    - Текущую конфигурацию
    - События изменений (для восстановления промежуточных состояний)
    
    Returns:
        Эталонная конфигурация, текущая конфигурация и события изменений
    """
    # Проверяем, что ПК существует
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем эталонную конфигурацию
    baseline = config_repo.find_baseline(pc_id)
    
    # Получаем текущую конфигурацию
    current_config = current_config_repo.find_by_pc_id(pc_id)
    
    # Получаем события изменений
    from infrastructure.database.repositories.event_repository import EventRepository
    event_repo = EventRepository(db)
    events = event_repo.find_by_pc_id(pc_id, skip=skip, limit=limit)
    total_events = event_repo.count_by_pc_id(pc_id)
    
    items = []
    
    # Добавляем эталонную конфигурацию
    if baseline:
        items.append(baseline.to_dict())
    
    # Добавляем текущую конфигурацию (если она отличается от эталонной)
    if current_config:
        current_dict = current_config.to_dict()
        # Преобразуем в формат PCConfiguration для совместимости
        current_dict['id'] = None  # У текущей конфигурации нет id в истории
        current_dict['is_baseline'] = False
        current_dict['timestamp'] = current_dict.get('updated_at')
        items.append(current_dict)
    
    return {
        "pc_id": pc_id,
        "total": len(items),
        "items": items,
        "events": {
            "total": total_events,
            "items": [event.to_dict() for event in events]
        }
    }


@router.get("/{pc_id}/history/graph")
async def get_pc_history_graph(
    pc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository),
    config_repo: ConfigRepository = Depends(get_config_repository),
    current_config_repo: CurrentConfigRepository = Depends(get_current_config_repository)
):
    """
    Получить данные для графа изменений конфигурации ПК
    
    Граф строится на основе:
    - Эталонной конфигурации (baseline)
    - Изменений (ChangeEvent) - группируются по времени
    - Текущей конфигурации
    
    Returns:
        Граф с узлами (эталонная, моменты изменений, текущая) и рёбрами (изменения)
    """
    from infrastructure.database.models import ChangeEvent
    from infrastructure.database.repositories.event_repository import EventRepository
    from collections import defaultdict
    
    # Проверяем, что ПК существует
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем эталонную конфигурацию
    baseline = config_repo.find_baseline(pc_id)
    
    # Получаем все изменения в хронологическом порядке
    event_repo = EventRepository(db)
    all_events = event_repo.find_by_pc_id(pc_id, skip=0, limit=10000)  # Получаем все события
    all_events.sort(key=lambda e: e.timestamp)  # Сортируем по времени (от старых к новым)
    
    # Получаем текущую конфигурацию
    current_config = current_config_repo.find_by_pc_id(pc_id)
    
    nodes = []
    edges = []
    
    # Узел 1: Эталонная конфигурация
    if baseline:
        baseline_timestamp = baseline.timestamp.isoformat() if baseline.timestamp else ""
        baseline_date_str = baseline.timestamp.strftime("%Y-%m-%d %H:%M") if baseline.timestamp else ""
        nodes.append({
            "id": "baseline",
            "label": f"Эталон\n{baseline_date_str}",
            "title": f"Эталонная конфигурация\nВремя: {baseline_timestamp}",
            "color": "#28a745",
            "shape": "diamond",
            "size": 25,
            "type": "baseline",
            "timestamp": baseline_timestamp
        })
    
    # Группируем события по времени (с точностью до секунды)
    events_by_time = defaultdict(list)
    for event in all_events:
        # Округляем до секунды для группировки
        time_key = event.timestamp.replace(microsecond=0) if event.timestamp else None
        if time_key:
            events_by_time[time_key].append(event)
    
    # Создаем узлы для моментов изменений
    change_nodes = {}
    node_counter = 1
    
    for time_key in sorted(events_by_time.keys()):
        events_at_time = events_by_time[time_key]
        time_str = time_key.isoformat()
        date_str = time_key.strftime("%Y-%m-%d %H:%M")
        
        # Подсчитываем типы изменений
        change_types = [e.event_type for e in events_at_time]
        change_components = list(set([e.component_type for e in events_at_time]))
        
        node_id = f"change_{node_counter}"
        change_nodes[time_key] = node_id
        node_counter += 1
        
        # Определяем цвет узла в зависимости от типа изменений
        if 'removed' in change_types:
            node_color = "#dc3545"  # красный - удаление
        elif 'added' in change_types:
            node_color = "#28a745"  # зелёный - добавление
        else:
            node_color = "#ffc107"  # жёлтый - замена
        
        nodes.append({
            "id": node_id,
            "label": f"Изменения\n{date_str}",
            "title": f"Изменения: {len(events_at_time)} событий\nКомпоненты: {', '.join(change_components)}\nТипы: {', '.join(set(change_types))}",
            "color": node_color,
            "shape": "dot",
            "size": 20,
            "type": "change",
            "timestamp": time_str,
            "event_count": len(events_at_time)
        })
    
    # Узел: Текущая конфигурация
    if current_config:
        current_timestamp = current_config.updated_at.isoformat() if current_config.updated_at else ""
        current_date_str = current_config.updated_at.strftime("%Y-%m-%d %H:%M") if current_config.updated_at else "Текущая"
        nodes.append({
            "id": "current",
            "label": f"Текущая\n{current_date_str}",
            "title": f"Текущая конфигурация\nВремя: {current_timestamp}",
            "color": "#007bff",
            "shape": "star",
            "size": 25,
            "type": "current",
            "timestamp": current_timestamp
        })
    
    # Создаем рёбра
    if baseline and change_nodes:
        # Ребро от эталонной к первому изменению
        first_change_time = min(change_nodes.keys())
        first_change_id = change_nodes[first_change_time]
        events_at_first = events_by_time[first_change_time]
        
        change_types = [e.event_type for e in events_at_first]
        change_components = list(set([e.component_type for e in events_at_first]))
        
        if 'removed' in change_types:
            edge_color = "#dc3545"
        elif 'added' in change_types:
            edge_color = "#28a745"
        else:
            edge_color = "#ffc107"
        
        edges.append({
            "from": "baseline",
            "to": first_change_id,
            "label": f"{len(events_at_first)} изменений",
            "title": f"Изменения: {', '.join(change_components)}\nТипы: {', '.join(set(change_types))}",
            "color": {"color": edge_color},
            "arrows": "to",
            "width": min(len(events_at_first) * 2, 10)
        })
        
        # Рёбра между изменениями
        sorted_times = sorted(change_nodes.keys())
        for i in range(len(sorted_times) - 1):
            prev_time = sorted_times[i]
            next_time = sorted_times[i + 1]
            prev_id = change_nodes[prev_time]
            next_id = change_nodes[next_time]
            
            events_at_next = events_by_time[next_time]
            change_types = [e.event_type for e in events_at_next]
            change_components = list(set([e.component_type for e in events_at_next]))
            
            if 'removed' in change_types:
                edge_color = "#dc3545"
            elif 'added' in change_types:
                edge_color = "#28a745"
            else:
                edge_color = "#ffc107"
            
            edges.append({
                "from": prev_id,
                "to": next_id,
                "label": f"{len(events_at_next)} изменений",
                "title": f"Изменения: {', '.join(change_components)}\nТипы: {', '.join(set(change_types))}",
                "color": {"color": edge_color},
                "arrows": "to",
                "width": min(len(events_at_next) * 2, 10)
            })
        
        # Ребро от последнего изменения к текущей конфигурации
        if current_config:
            last_change_time = max(change_nodes.keys())
            last_change_id = change_nodes[last_change_time]
            edges.append({
                "from": last_change_id,
                "to": "current",
                "label": "Текущее состояние",
                "title": "Текущая конфигурация",
                "color": {"color": "#007bff"},
                "arrows": "to",
                "width": 2
            })
    elif baseline and current_config:
        # Нет изменений, но есть эталонная и текущая
        edges.append({
            "from": "baseline",
            "to": "current",
            "label": "Без изменений",
            "title": "Конфигурация не изменилась",
            "color": {"color": "#6c757d"},
            "arrows": "to",
            "width": 1,
            "dashes": True
        })
    
    return {
        "nodes": nodes,
        "edges": edges
    }


@router.get("/{pc_id}", response_model=PCDetailResponse)
async def get_pc(
    pc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository),
    config_repo: ConfigRepository = Depends(get_config_repository),
    current_config_repo: CurrentConfigRepository = Depends(get_current_config_repository)
):
    """Получить информацию о ПК"""
    # Обновляем статус offline перед получением информации
    pc_repo.update_offline_status(offline_threshold_minutes=10)
    
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем текущее состояние конфигурации
    current_config = current_config_repo.find_by_pc_id(pc_id)
    
    # Получаем эталонную конфигурацию из истории
    baseline = config_repo.find_baseline(pc_id)
    
    result = pc.to_dict()
    result['current_config'] = current_config.to_dict() if current_config else None
    result['baseline_config'] = baseline.to_dict() if baseline else None
    
    return result


@router.get("/{pc_id}/events", response_model=dict)
async def get_pc_events(
    pc_id: str,
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить события для ПК"""
    from infrastructure.database.repositories.event_repository import EventRepository
    
    event_repo = EventRepository(db)
    events = event_repo.find_by_pc_id(pc_id, skip=skip, limit=limit)
    total = event_repo.count_by_pc_id(pc_id)
    
    return {
        "total": total,
        "items": [event.to_dict() for event in events]
    }


@router.post("/{pc_id}/baseline", response_model=SetBaselineResponse)
async def set_baseline(
    pc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository),
    config_repo: ConfigRepository = Depends(get_config_repository)
):
    """Установить текущую конфигурацию как эталонную"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем текущую конфигурацию из истории (последнюю запись)
    # Используем прямую выборку для оптимизации
    from infrastructure.database.models import PCConfiguration
    latest = (
        db.query(PCConfiguration)
        .filter(PCConfiguration.pc_id == pc_id)
        .order_by(PCConfiguration.timestamp.desc(), PCConfiguration.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No configuration found")
    
    # Устанавливаем новую эталонную
    config_repo.update_baseline(pc_id, latest)
    
    # Обновляем статус ПК
    pc.status = 'normal'
    pc_repo.update(pc)
    db.commit()
    
    return SetBaselineResponse(message="Baseline configuration updated", pc_id=pc_id)


@router.patch("/{pc_id}/location", response_model=dict)
async def update_pc_location_endpoint(
    pc_id: str,
    request_data: UpdateLocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository)
):
    """Обновить локацию ПК"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    update_pc_location(pc, request_data.location)
    pc_repo.update(pc)
    db.commit()
    
    return {"message": "Location updated", "pc_id": pc_id, "location": pc.location}


@router.post("/bulk-update-locations", response_model=BulkUpdateLocationResponse)
async def bulk_update_locations(
    request_data: BulkUpdateLocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository)
):
    """Массовое обновление локаций ПК"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    updated = 0
    failed = 0
    errors = []
    
    for update_item in request_data.updates:
        pc_id = update_item.get('pc_id')
        location = update_item.get('location')
        
        if not pc_id:
            failed += 1
            errors.append(f"Missing pc_id in update item")
            continue
        
        pc = pc_repo.find_by_id(pc_id)
        if not pc:
            failed += 1
            errors.append(f"PC not found: {pc_id}")
            continue
        
        try:
            update_pc_location(pc, location)
            pc_repo.update(pc)
            updated += 1
        except Exception as e:
            failed += 1
            errors.append(f"Error updating {pc_id}: {str(e)}")
    
    db.commit()
    
    return BulkUpdateLocationResponse(
        updated=updated,
        failed=failed,
        errors=errors
    )


@router.post("/bulk-update-locations-from-file", response_model=BulkUpdateLocationResponse)
async def bulk_update_locations_from_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    pc_repo: PCRepository = Depends(get_pc_repository)
):
    """Массовое обновление локаций из CSV файла
    
    Формат CSV: pc_id,location
    Пример:
    PGXWK0MCYFF2GS_pcman,D752
    ABC123_hostname,площадка ICPC
    """
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be CSV")
    
    content = await file.read()
    text_content = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(text_content))
    
    updated = 0
    failed = 0
    errors = []
    
    for row in csv_reader:
        pc_id = row.get('pc_id', '').strip()
        location = row.get('location', '').strip()
        
        if not pc_id:
            failed += 1
            errors.append(f"Missing pc_id in row: {row}")
            continue
        
        pc = pc_repo.find_by_id(pc_id)
        if not pc:
            failed += 1
            errors.append(f"PC not found: {pc_id}")
            continue
        
        try:
            update_pc_location(pc, location if location else None)
            pc_repo.update(pc)
            updated += 1
        except Exception as e:
            failed += 1
            errors.append(f"Error updating {pc_id}: {str(e)}")
    
    db.commit()
    
    return BulkUpdateLocationResponse(
        updated=updated,
        failed=failed,
        errors=errors
    )

