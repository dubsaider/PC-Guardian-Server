"""
Kafka Consumer для получения данных от агентов
Инфраструктурный слой - только работа с Kafka
"""
import json
import logging
import threading
from datetime import datetime
from typing import Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError

from infrastructure.kafka.config import KafkaConfig
from common.models import PCConfiguration
from core.services.configuration_processing_service import ConfigurationProcessingService


class PCGuardianConsumer:
    """
    Kafka Consumer для обработки конфигураций ПК
    Инфраструктурный слой - только работа с Kafka
    Бизнес-логика вынесена в ConfigurationProcessingService
    """
    
    def __init__(self, kafka_config: Optional[KafkaConfig] = None):
        """
        Инициализация Consumer
        
        Args:
            kafka_config: Конфигурация Kafka
        """
        self.kafka_config = kafka_config or KafkaConfig()
        self.consumer = None
        self.running = False
        
        # Сервис обработки конфигураций (бизнес-логика)
        self.processing_service = ConfigurationProcessingService()
        
        # Настройка логирования
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
        try:
            # Логирование входящих данных для отладки (INFO уровень, чтобы видеть в логах)
            agent_ver = config_data.get('agent_version')
            network_adapters = config_data.get('network_adapters', [])
            ip_count = 0
            if network_adapters:
                for adapter in network_adapters:
                    if isinstance(adapter, dict):
                        ips = adapter.get('ip_addresses', [])
                        if ips:
                            ip_count += len(ips)
            
            self.logger.info(
                f"Received config from Kafka: pc_id={config_data.get('pc_id')}, "
                f"agent_version={agent_ver}, "
                f"network_adapters_count={len(network_adapters) if network_adapters else 0}, "
                f"total_ip_addresses={ip_count}"
            )
            
            # Парсим конфигурацию из JSON в domain модель
            config = PCConfiguration.from_dict(config_data)
            
            # Логирование после парсинга
            parsed_ip_count = 0
            if config.network_adapters:
                for adapter in config.network_adapters:
                    if adapter.ip_addresses:
                        parsed_ip_count += len(adapter.ip_addresses)
            
            self.logger.info(
                f"Parsed config: pc_id={config.pc_id}, "
                f"agent_version={config.agent_version}, "
                f"network_adapters_count={len(config.network_adapters) if config.network_adapters else 0}, "
                f"parsed_ip_addresses={parsed_ip_count}"
            )
            
            # Передаем обработку сервису (бизнес-логика)
            self.processing_service.process_configuration(config)
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки конфигурации: {e}", exc_info=True)
            raise
    
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
            self.logger.info("Kafka Consumer started, waiting for messages...")
            message_count = 0
            while self.running:
                try:
                    message_pack = self.consumer.poll(timeout_ms=1000)
                    
                    if not message_pack:
                        # Нет сообщений, но consumer работает
                        continue
                    
                    for topic_partition, messages in message_pack.items():
                        for message in messages:
                            # #region agent log
                            try:
                                with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({"id":"log_kafka_message_received","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:129","message":"Получено сообщение из Kafka","data":{"offset":message.offset if hasattr(message,'offset') else None,"partition":topic_partition.partition if hasattr(topic_partition,'partition') else None},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                            except: pass
                            # #endregion
                            try:
                                config_data = message.value
                                self.logger.info(f"Received message from Kafka: pc_id={config_data.get('pc_id')}")
                                # #region agent log
                                try:
                                    with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":"log_kafka_before_process","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:133","message":"Перед обработкой сообщения","data":{"pc_id":config_data.get('pc_id'),"offset":message.offset if hasattr(message,'offset') else None},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                                except: pass
                                # #endregion
                                self._process_configuration(config_data)
                                # #region agent log
                                try:
                                    with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":"log_kafka_after_process","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:133","message":"После успешной обработки сообщения","data":{"pc_id":config_data.get('pc_id'),"offset":message.offset if hasattr(message,'offset') else None},"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                                except: pass
                                # #endregion
                            except Exception as e:
                                # #region agent log
                                try:
                                    with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                        f.write(json.dumps({"id":"log_kafka_error","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:160","message":"Ошибка обработки сообщения","data":{"error":str(e),"offset":message.offset if hasattr(message,'offset') else None},"sessionId":"debug-session","runId":"post-fix","hypothesisId":"B"}) + '\n')
                                except: pass
                                # #endregion
                                self.logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
                                # ИСПРАВЛЕНИЕ БАГА B: При ошибке обработки коммитим offset вручную, чтобы не зациклиться
                                # Это позволяет пропустить проблемное сообщение и продолжить обработку следующих
                                try:
                                    self.consumer.commit()
                                    # #region agent log
                                    try:
                                        with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                            f.write(json.dumps({"id":"log_kafka_error_committed","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:167","message":"Offset закоммичен после ошибки - сообщение пропущено","data":{"offset":message.offset if hasattr(message,'offset') else None},"sessionId":"debug-session","runId":"post-fix","hypothesisId":"B"}) + '\n')
                                    except: pass
                                    # #endregion
                                except Exception as commit_err:
                                    self.logger.error(f"Ошибка коммита offset после ошибки обработки: {commit_err}")
                
                except KafkaError as e:
                    # #region agent log
                    try:
                        with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":"log_kafka_error_recreate","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:182","message":"Ошибка Kafka - пересоздание consumer с задержкой","data":{"error":str(e)},"sessionId":"debug-session","runId":"post-fix","hypothesisId":"E"}) + '\n')
                    except: pass
                    # #endregion
                    self.logger.error(f"Ошибка Kafka: {e}")
                    # ИСПРАВЛЕНИЕ БАГА E: Пересоздаем consumer при ошибке с задержкой, чтобы избежать бесконечного цикла
                    try:
                        self.consumer.close()
                    except:
                        pass
                    self.consumer = None
                    # Добавляем задержку перед пересозданием (5 секунд)
                    import time
                    time.sleep(5)
                    # #region agent log
                    try:
                        with open(r'c:\Users\Vladislav\Projects\PC-Guardian-Server\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"id":"log_kafka_recreate_after_delay","timestamp":int(datetime.utcnow().timestamp()*1000),"location":"consumer.py:195","message":"Пересоздание consumer после задержки","data":{},"sessionId":"debug-session","runId":"post-fix","hypothesisId":"E"}) + '\n')
                    except: pass
                    # #endregion
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
