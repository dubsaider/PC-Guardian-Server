"""
Сервис для сравнения конфигураций
Бизнес-логика сравнения и обработки изменений
"""
import logging
from typing import List

from infrastructure.database.models import PCConfiguration as DBPCConfiguration
from core.domain.comparators.config_comparator import ConfigComparator
from common.models import ChangeEvent


class ComparisonService:
    """Сервис для сравнения конфигураций ПК"""
    
    def __init__(self):
        self.comparator = ConfigComparator()
        self.logger = logging.getLogger(__name__)
    
    def compare_configurations(
        self,
        baseline: DBPCConfiguration,
        current: DBPCConfiguration
    ) -> List[ChangeEvent]:
        """
        Сравнить эталонную и текущую конфигурации
        
        Args:
            baseline: Эталонная конфигурация
            current: Текущая конфигурация
            
        Returns:
            Список событий изменений (domain модели)
        """
        return self.comparator.compare_configurations(baseline, current)









