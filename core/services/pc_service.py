"""
Сервис для работы с ПК
Бизнес-логика работы с ПК
"""
import logging
from datetime import datetime
from typing import Optional

from infrastructure.database.models import PC
from infrastructure.database.repositories.pc_repository import PCRepository
from common.location_parser import update_pc_location


class PCService:
    """Сервис для работы с ПК"""
    
    def __init__(self, pc_repository: PCRepository):
        self.pc_repository = pc_repository
        self.logger = logging.getLogger(__name__)
    
    def find_or_create_pc(self, pc_id: str, hostname: str, last_seen: Optional[datetime] = None) -> PC:
        """
        Найти ПК или создать новый
        
        Args:
            pc_id: ID ПК
            hostname: Имя хоста
            last_seen: Время последнего контакта
            
        Returns:
            Объект ПК
        """
        pc = self.pc_repository.find_by_id(pc_id)
        
        if not pc:
            # Создаем новый ПК
            pc = PC(
                pc_id=pc_id,
                hostname=hostname,
                status='normal',
                last_seen=last_seen or datetime.utcnow()
            )
            self.pc_repository.create(pc)
            self.logger.info(f"Зарегистрирован новый ПК: {pc_id} ({hostname})")
        else:
            # Обновляем время последнего контакта
            if last_seen:
                pc.last_seen = last_seen
                # Если устройство было offline, но пришла новая конфигурация,
                # временно возвращаем статус в 'normal' (окончательный статус определится при обработке конфигурации)
                if pc.status == 'offline':
                    pc.status = 'normal'
                    self.logger.info(f"ПК {pc_id} ({hostname}) снова онлайн, статус изменен с 'offline' на 'normal'")
            self.pc_repository.update(pc)
        
        return pc
    
    def update_status(self, pc: PC, status: str) -> PC:
        """
        Обновить статус ПК
        
        Args:
            pc: Объект ПК
            status: Новый статус
            
        Returns:
            Обновленный объект ПК
        """
        pc.status = status
        self.pc_repository.update(pc)
        return pc
    
    def update_last_seen(self, pc: PC, last_seen: datetime) -> PC:
        """
        Обновить время последнего контакта
        
        Args:
            pc: Объект ПК
            last_seen: Время последнего контакта
            
        Returns:
            Обновленный объект ПК
        """
        pc.last_seen = last_seen
        # Если устройство было offline, но обновляется last_seen,
        # временно возвращаем статус в 'normal' (окончательный статус определится при обработке конфигурации)
        if pc.status == 'offline':
            pc.status = 'normal'
            self.logger.info(f"ПК {pc.pc_id} ({pc.hostname}) снова онлайн, статус изменен с 'offline' на 'normal'")
        self.pc_repository.update(pc)
        return pc



