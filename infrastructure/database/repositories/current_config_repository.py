"""
Репозиторий для работы с текущим состоянием конфигураций ПК
"""
import json
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional

from infrastructure.database.models import PCCurrentConfiguration


class CurrentConfigRepository:
    """Репозиторий для работы с текущим состоянием конфигураций ПК"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_by_pc_id(self, pc_id: str) -> Optional[PCCurrentConfiguration]:
        """Найти текущее состояние конфигурации для ПК"""
        return self.db.query(PCCurrentConfiguration).filter_by(pc_id=pc_id).first()
    
    def find_all(self, pc_ids: list[str] = None) -> list[PCCurrentConfiguration]:
        """Найти текущее состояние для списка ПК или всех ПК"""
        query = self.db.query(PCCurrentConfiguration)
        if pc_ids:
            query = query.filter(PCCurrentConfiguration.pc_id.in_(pc_ids))
        return query.all()
    
    def create_or_update(self, current_config: PCCurrentConfiguration) -> PCCurrentConfiguration:
        """Создать или обновить текущее состояние конфигурации"""
        thread_id = threading.current_thread().ident
        # #region agent log
        try:
            with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({"id":"log_current_config_start","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"current_config_repository.py:27","message":"Начало create_or_update","data":{"pc_id":current_config.pc_id,"thread_id":thread_id},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
        except: pass
        # #endregion
        existing = self.find_by_pc_id(current_config.pc_id)
        if existing:
            # #region agent log
            try:
                with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":"log_current_config_update","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"current_config_repository.py:30","message":"Обновление существующей записи","data":{"pc_id":current_config.pc_id,"thread_id":thread_id,"existing_updated_at":str(existing.updated_at) if existing.updated_at else None},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
            except: pass
            # #endregion
            # Обновляем существующую запись
            for key, value in current_config.to_dict().items():
                if key != 'pc_id':  # Не обновляем первичный ключ
                    setattr(existing, key, getattr(current_config, key, None))
            existing.updated_at = current_config.updated_at
            # #region agent log
            try:
                with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":"log_current_config_updated","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"current_config_repository.py:35","message":"Запись обновлена","data":{"pc_id":current_config.pc_id,"thread_id":thread_id,"new_updated_at":str(existing.updated_at) if existing.updated_at else None},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
            except: pass
            # #endregion
            return existing
        else:
            # #region agent log
            try:
                with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"id":"log_current_config_create","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"current_config_repository.py:38","message":"Создание новой записи","data":{"pc_id":current_config.pc_id,"thread_id":thread_id},"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + '\n')
            except: pass
            # #endregion
            # Создаем новую запись
            self.db.add(current_config)
            self.db.flush()
            return current_config
    
