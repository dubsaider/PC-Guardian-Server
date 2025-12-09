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
    
    pcs = pc_repo.find_all(
        skip=skip, 
        limit=limit, 
        status=status,
        building=building,
        floor=floor,
        location=location,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )
    total = pc_repo.count_all(
        status=status,
        building=building,
        floor=floor,
        location=location,
        search=search
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
    config_repo: ConfigRepository = Depends(get_config_repository)
):
    """
    Получить историю изменений конфигурации ПК
    
    Returns:
        Список всех конфигураций ПК в хронологическом порядке
    """
    # Проверяем, что ПК существует
    pc = pc_repo.find_by_id(pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="PC not found")
    
    # Получаем все конфигурации для ПК
    from infrastructure.database.models import PCConfiguration
    configs = (
        db.query(PCConfiguration)
        .filter(PCConfiguration.pc_id == pc_id)
        .order_by(PCConfiguration.timestamp.desc(), PCConfiguration.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    total = (
        db.query(PCConfiguration)
        .filter(PCConfiguration.pc_id == pc_id)
        .count()
    )
    
    return {
        "pc_id": pc_id,
        "total": total,
        "items": [config.to_dict() for config in configs]
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

