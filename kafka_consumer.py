"""
Kafka Consumer для получения данных от агентов
"""
import json
import logging
import threading
from typing import Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from common.kafka_config import KafkaConfig
from common.models import PCConfiguration
from database import SessionLocal, PC, PCConfiguration as DBPCConfiguration, ChangeEvent, Base, engine
from config_comparator import ConfigComparator
from notifications import NotificationService


class PCGuardianConsumer:
    """Kafka Consumer для обработки конфигураций ПК"""
    
    def __init__(self, kafka_config: Optional[KafkaConfig] = None):
        """
        Инициализация Consumer
        
        Args:
            kafka_config: Конфигурация Kafka
        """
        self.kafka_config = kafka_config or KafkaConfig()
        self.consumer = None
        self.running = False
        self.comparator = ConfigComparator()
        self.notification_service = NotificationService()
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_consumer(self):
        """Создать Kafka Consumer"""
        try:
            config = self.kafka_config.get_consumer_config()
            self.consumer = KafkaConsumer(
                self.kafka_config.topic,
                **config,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=1000
            )
            self.logger.info("Kafka Consumer создан успешно")
        except Exception as e:
            self.logger.error(f"Ошибка создания Kafka Consumer: {e}")
            raise
    
    def _process_configuration(self, config_data: dict):
        """Обработать полученную конфигурацию"""
        db = SessionLocal()
        try:
            # Парсим конфигурацию
            config = PCConfiguration.from_dict(config_data)
            
            # Проверяем, существует ли ПК
            pc = db.query(PC).filter_by(pc_id=config.pc_id).first()
            
            if not pc:
                # Регистрируем новый ПК
                pc = PC(
                    pc_id=config.pc_id,
                    hostname=config.hostname,
                    status='normal'
                )
                db.add(pc)
                db.flush()
                
                # Создаем эталонную конфигурацию
                baseline = self._create_db_configuration(pc.pc_id, config, is_baseline=True)
                db.add(baseline)
                
                self.logger.info(f"Зарегистрирован новый ПК: {config.pc_id} ({config.hostname})")
            else:
                # Обновляем время последнего контакта
                pc.last_seen = config.timestamp
                
                # Получаем эталонную конфигурацию
                baseline = db.query(DBPCConfiguration).filter_by(
                    pc_id=pc.pc_id,
                    is_baseline=True
                ).first()
                
                if baseline:
                    # Сравниваем с эталонной
                    current_db_config = self._create_db_configuration(pc.pc_id, config, is_baseline=False)
                    events = self.comparator.compare_configurations(baseline, current_db_config)
                    
                    if events:
                        # Есть изменения
                        pc.status = 'changed'
                        
                        # Сохраняем события
                        for event in events:
                            db_event = ChangeEvent(
                                pc_id=pc.pc_id,
                                component_type=event.component_type,
                                event_type=event.event_type,
                                timestamp=event.timestamp,
                                details=event.details
                            )
                            db_event.set_old_value(event.old_value)
                            db_event.set_new_value(event.new_value)
                            db.add(db_event)
                            
                            # Отправляем уведомление
                            self.notification_service.send_alert(pc, event)
                        
                        self.logger.warning(
                            f"Обнаружены изменения на ПК {config.pc_id}: {len(events)} событий"
                        )
                    else:
                        # Изменений нет
                        pc.status = 'normal'
                    
                    # Сохраняем текущую конфигурацию
                    db.add(current_db_config)
                else:
                    # Нет эталонной конфигурации, создаем её
                    baseline = self._create_db_configuration(pc.pc_id, config, is_baseline=True)
                    db.add(baseline)
                    pc.status = 'normal'
                    self.logger.info(f"Создана эталонная конфигурация для ПК: {config.pc_id}")
            
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки конфигурации: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def _create_db_configuration(self, pc_id: str, config: PCConfiguration, is_baseline: bool) -> DBPCConfiguration:
        """Создать объект конфигурации для БД"""
        db_config = DBPCConfiguration(
            pc_id=pc_id,
            is_baseline=is_baseline,
            timestamp=config.timestamp or config.timestamp
        )
        
        if config.motherboard:
            db_config.set_component('motherboard', config.motherboard.to_dict())
        if config.cpu:
            db_config.set_component('cpu', config.cpu.to_dict())
        if config.ram_modules:
            db_config.set_component('ram_modules', [m.to_dict() for m in config.ram_modules])
        if config.storage_devices:
            db_config.set_component('storage_devices', [s.to_dict() for s in config.storage_devices])
        if config.gpu:
            db_config.set_component('gpu', config.gpu.to_dict())
        if config.network_adapters:
            db_config.set_component('network_adapters', [n.to_dict() for n in config.network_adapters])
        if config.psu:
            db_config.set_component('psu', config.psu.to_dict())
        
        return db_config
    
    def start(self):
        """Запустить Consumer в отдельном потоке"""
        if self.running:
            self.logger.warning("Consumer уже запущен")
            return
        
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        self.logger.info("Kafka Consumer запущен в фоновом режиме")
    
    def _run(self):
        """Основной цикл Consumer"""
        if not self.consumer:
            self._create_consumer()
        
        try:
            while self.running:
                try:
                    message_pack = self.consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_pack.items():
                        for message in messages:
                            try:
                                config_data = message.value
                                self._process_configuration(config_data)
                            except Exception as e:
                                self.logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
                
                except KafkaError as e:
                    self.logger.error(f"Ошибка Kafka: {e}")
                    # Пересоздаем consumer при ошибке
                    try:
                        self.consumer.close()
                    except:
                        pass
                    self.consumer = None
                    self._create_consumer()
                
        except Exception as e:
            self.logger.error(f"Критическая ошибка в Consumer: {e}", exc_info=True)
        finally:
            if self.consumer:
                try:
                    self.consumer.close()
                except:
                    pass
    
    def stop(self):
        """Остановить Consumer"""
        self.running = False
        if self.consumer:
            try:
                self.consumer.close()
            except:
                pass
        self.logger.info("Kafka Consumer остановлен")

