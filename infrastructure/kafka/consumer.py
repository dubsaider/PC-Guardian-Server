"""
Kafka Consumer для получения данных от агентов
Инфраструктурный слой - только работа с Kafka
"""
import json
import logging
import threading
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
                            try:
                                config_data = message.value
                                self.logger.info(f"Received message from Kafka: pc_id={config_data.get('pc_id')}")
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
