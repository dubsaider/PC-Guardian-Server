"""
Сервис уведомлений для PC-Guardian
Использует обработчики для отправки через различные каналы
Логика проверки правил вынесена в AlertService
"""
import json
import logging
import os
import threading
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from infrastructure.database.models import PC, ChangeEvent, AlertRule as DBAlertRule
from infrastructure.messaging.handlers.telegram_handler import TelegramHandler
from infrastructure.messaging.handlers.email_handler import EmailHandler
from core.services.alert_service import AlertService
from core.config import settings


class NotificationService:
    """Сервис для отправки уведомлений через различные каналы"""
    
    # Класс-переменные для общего буфера (общие для всех экземпляров)
    # Буфер хранит данные в виде (pc_data, event_data, message, subject, timestamp)
    # где pc_data и event_data - словари с данными (не объекты SQLAlchemy)
    _email_buffer: Dict[Tuple[tuple, Optional[int]], List[Tuple[dict, dict, str, str, datetime]]] = defaultdict(list)
    _buffer_lock = threading.Lock()
    _flush_timer: Optional[threading.Timer] = None
    
    def __init__(self, alert_service: Optional[AlertService] = None):
        self.logger = logging.getLogger(__name__)
        self.alert_service = alert_service
        
        # Инициализируем обработчики
        self.telegram_handler = TelegramHandler()
        self.email_handler = EmailHandler()
        
        # Настройки группировки уведомлений (глобальные, используются если правило не указывает)
        self.email_grouping_window_seconds = settings.email_grouping_window_seconds
    
    def send_alert(self, pc: PC, event: ChangeEvent, user_id: Optional[int] = None):
        """
        Отправить уведомление об изменении согласно правилам
        
        Args:
            pc: Объект ПК
            event: Событие изменения
            user_id: ID пользователя (для фильтрации правил)
        """
        message = self._format_alert_message(pc, event)
        subject = f"PC-Guardian: {pc.hostname} — {event.event_type}"
        
        # Если есть сервис правил - используем его
        if self.alert_service:
            matching_rules = self.alert_service.get_matching_rules(pc, event, user_id)
            
            if not matching_rules:
                self.logger.debug(f"Нет правил уведомлений для события {event.id}")
                return
            
            # Отправляем уведомления согласно правилам
            for rule_idx, rule in enumerate(matching_rules):
                channels = rule.get_channels()
                recipients = rule.get_recipients()
                
                if 'email' in channels:
                    email_recipients = [r for r in recipients if '@' in r]  # Фильтруем email адреса
                    if email_recipients:
                        try:
                            # Проверяем настройку группировки из правила
                            # rule - это DBAlertRule, у него есть поле email_grouping_enabled
                            rule_grouping_enabled = rule.email_grouping_enabled if hasattr(rule, 'email_grouping_enabled') else True
                            
                            if rule_grouping_enabled:
                                # Добавляем в буфер для группировки
                                self._add_to_email_buffer(email_recipients, rule.id if hasattr(rule, 'id') else None, pc, event, message, subject)
                                self.logger.debug(f"Email добавлен в буфер для группировки (правило {rule_idx})")
                            else:
                                # Отправляем сразу (отдельные письма)
                                result = self.email_handler.send(message, subject, email_recipients)
                                self.logger.debug(f"Email отправлен для правила {rule_idx}: {result}")
                        except Exception as email_err:
                            self.logger.error(f"Ошибка отправки email для правила {rule_idx}: {email_err}", exc_info=True)
                            raise
                
                if 'telegram' in channels:
                    telegram_recipients = [r for r in recipients if '@' not in r]  # Фильтруем telegram chat_id
                    if telegram_recipients:
                        try:
                            result = self.telegram_handler.send(message, telegram_recipients)
                            self.logger.debug(f"Telegram отправлен для правила {rule_idx}: {result}")
                        except Exception as telegram_err:
                            self.logger.error(f"Ошибка отправки telegram для правила {rule_idx}: {telegram_err}", exc_info=True)
                            raise
            
            # Помечаем событие как уведомленное
            # Если используется группировка, событие уже добавлено в буфер и будет отправлено
            event.notified = True
            event.notified_at = datetime.now(timezone.utc)
        else:
            # Fallback: отправляем через все доступные каналы (старое поведение)
            if self.telegram_handler.is_enabled():
                self.telegram_handler.send(message)
            
            if self.email_handler.is_enabled():
                self.email_handler.send(message, subject)
    
    def _format_alert_message(self, pc: PC, event: ChangeEvent) -> str:
        """Форматировать сообщение об изменении"""
        event_type_ru = {
            'removed': 'удален',
            'added': 'добавлен',
            'replaced': 'заменен'
        }
        
        component_type_ru = {
            'motherboard': 'Материнская плата',
            'cpu': 'Процессор',
            'ram': 'Оперативная память',
            'storage': 'Накопитель',
            'gpu': 'Видеокарта',
            'network': 'Сетевой адаптер',
            'psu': 'Блок питания',
            'peripherals': 'Периферийные устройства'
        }
        
        event_type = event_type_ru.get(event.event_type, event.event_type)
        component_type = component_type_ru.get(event.component_type, event.component_type)
        
        # Время с учетом локальной таймзоны
        event_time_local = event.timestamp
        if event_time_local:
            if event_time_local.tzinfo is None:
                event_time_local = event_time_local.replace(tzinfo=timezone.utc)
            local_tz = datetime.now().astimezone().tzinfo
            event_time_local = event_time_local.astimezone(local_tz)
            time_str = event_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            time_str = "неизвестно"

        # Локация
        location_lines = []
        if pc.location:
            location_lines.append(f"Локация: {pc.location}")
        if pc.building:
            location_lines.append(f"Корпус: {pc.building}")
        if pc.floor:
            location_lines.append(f"Этаж: {pc.floor}")
        location_block = "\n".join(location_lines) if location_lines else "Локация: не указана"

        message = (
            "⚠️ ВНИМАНИЕ: Изменение конфигурации ПК\n\n"
            f"ПК: {pc.hostname} ({pc.pc_id})\n"
            f"{location_block}\n"
            f"Компонент: {component_type}\n"
            f"Тип изменения: {event_type}\n"
            f"Время: {time_str}\n\n"
        )
        
        if event.details:
            message += f"Детали: {event.details}\n\n"
        
        if event.get_old_value():
            old_value = event.get_old_value()
            old_model = old_value.get('model') or old_value.get('name') or 'неизвестно'
            message += f"Было: {old_model}\n"
        
        if event.get_new_value():
            new_value = event.get_new_value()
            new_model = new_value.get('model') or new_value.get('name') or 'неизвестно'
            message += f"Стало: {new_model}\n"
        
        return message

    def _extract_pc_data_for_buffer(self, pc: PC) -> dict:
        """
        Извлечь данные ПК для буфера (до закрытия сессии)
        
        Args:
            pc: Объект ПК
            
        Returns:
            Словарь с данными ПК
        """
        # Извлекаем все необходимые атрибуты ДО закрытия сессии
        return {
            'pc_id': pc.pc_id,
            'hostname': pc.hostname,
            'location': pc.location,
            'building': pc.building,
            'floor': pc.floor,
            'status': pc.status
        }
    
    def _extract_event_data_for_buffer(self, event: ChangeEvent) -> dict:
        """
        Извлечь данные события для буфера (до закрытия сессии)
        
        Args:
            event: Объект события
            
        Returns:
            Словарь с данными события
        """
        # Извлекаем все необходимые атрибуты ДО закрытия сессии
        return {
            'id': event.id if hasattr(event, 'id') else None,
            'pc_id': event.pc_id,
            'component_type': event.component_type,
            'event_type': event.event_type,
            'timestamp': event.timestamp,
            'details': event.details,
            'old_value': event.get_old_value(),
            'new_value': event.get_new_value()
        }
    
    def _add_to_email_buffer(self, recipients: List[str], rule_id: Optional[int], pc: PC, event: ChangeEvent, message: str, subject: str):
        """
        Добавить уведомление в буфер для группировки
        
        Args:
            recipients: Список получателей
            rule_id: ID правила (для группировки по правилам)
            pc: Объект ПК
            event: Событие изменения
            message: Текст сообщения
            subject: Тема письма
        """
        with NotificationService._buffer_lock:
            recipients_tuple = tuple(sorted(recipients))  # Используем tuple для ключа
            key = (recipients_tuple, rule_id)
            timestamp = datetime.now(timezone.utc)
            
            # Извлекаем данные из объектов ДО добавления в буфер, чтобы избежать DetachedInstanceError
            pc_data = self._extract_pc_data_for_buffer(pc)
            event_data = self._extract_event_data_for_buffer(event)
            
            NotificationService._email_buffer[key].append((pc_data, event_data, message, subject, timestamp))
            self.logger.debug(f"Добавлено уведомление в буфер для {recipients}: {len(NotificationService._email_buffer[key])} уведомлений в буфере")
            
            # Запускаем таймер для отправки, если его еще нет
            if NotificationService._flush_timer is None or not NotificationService._flush_timer.is_alive():
                # Сохраняем ссылку на alert_service для использования в callback
                alert_service_ref = self.alert_service
                # Создаем лямбду, которая создаст новый экземпляр для вызова метода
                def flush_callback():
                    temp_instance = NotificationService(alert_service_ref)
                    temp_instance._flush_email_buffer()
                
                NotificationService._flush_timer = threading.Timer(
                    self.email_grouping_window_seconds,
                    flush_callback
                )
                NotificationService._flush_timer.start()
                self.logger.debug(f"Запущен таймер отправки группового письма через {self.email_grouping_window_seconds} секунд")
    
    def _flush_email_buffer(self):
        """
        Отправить все накопленные email уведомления как групповое письмо
        """
        self.logger.debug("Начало отправки накопленных email уведомлений")
        with NotificationService._buffer_lock:
            if not NotificationService._email_buffer:
                self.logger.debug("Буфер email уведомлений пуст")
                return
            
            # Копируем буфер и очищаем его
            buffer_copy = dict(NotificationService._email_buffer)
            self.logger.debug(f"Буфер скопирован: {len(buffer_copy)} групп получателей")
            NotificationService._email_buffer.clear()
            NotificationService._flush_timer = None
        
        # Отправляем групповые письма для каждой группы получателей
        for (recipients_tuple, rule_id), notifications in buffer_copy.items():
            self.logger.debug(f"Обработка группы: {len(notifications)} уведомлений для получателей {list(recipients_tuple)}")
            recipients = list(recipients_tuple)
            
            if len(notifications) == 1:
                # Если только одно уведомление - отправляем как обычно
                pc_data, event_data, message, subject, _ = notifications[0]
                try:
                    result = self.email_handler.send(message, subject, recipients)
                    self.logger.info(f"Отправлено одиночное email уведомление для {pc_data['hostname']}")
                except Exception as e:
                    self.logger.error(f"Ошибка отправки одиночного email уведомления: {e}")
            else:
                # Группируем несколько уведомлений в одно письмо
                try:
                    self.logger.debug(f"Формирование группового письма для {len(notifications)} уведомлений")
                    grouped_message = self._format_grouped_email(notifications)
                    
                    grouped_subject = f"PC-Guardian: Сводка изменений ({len(notifications)} устройств)"
                    
                    result = self.email_handler.send(grouped_message, grouped_subject, recipients)
                    self.logger.info(f"Отправлено групповое email уведомление для {len(notifications)} устройств получателям: {', '.join(recipients)}")
                except Exception as e:
                    self.logger.error(f"Ошибка отправки группового email уведомления: {e}", exc_info=True)
    
    def _format_grouped_email(self, notifications: List[Tuple[dict, dict, str, str, datetime]]) -> str:
        """
        Форматировать групповое email сообщение из нескольких уведомлений
        
        Args:
            notifications: Список кортежей (pc_data, event_data, message, subject, timestamp)
            где pc_data и event_data - словари с данными
            
        Returns:
            Отформатированное сообщение
        """
        self.logger.debug(f"Форматирование группового email: {len(notifications)} уведомлений")
        
        # Переводим типы событий и компонентов
        event_type_ru = {
            'removed': 'удален',
            'added': 'добавлен',
            'replaced': 'заменен'
        }
        
        component_type_ru = {
            'motherboard': 'Материнская плата',
            'cpu': 'Процессор',
            'ram': 'Оперативная память',
            'storage': 'Накопитель',
            'gpu': 'Видеокарта',
            'network': 'Сетевой адаптер',
            'psu': 'Блок питания',
            'peripherals': 'Периферийные устройства'
        }
        
        # Группируем по ПК
        pcs_events: Dict[str, List[Tuple[dict, dict, datetime]]] = defaultdict(list)
        for pc_data, event_data, message, subject, timestamp in notifications:
            pcs_events[pc_data['pc_id']].append((pc_data, event_data, timestamp))
        
        # Формируем заголовок
        header = (
            "⚠️ СВОДКА ИЗМЕНЕНИЙ КОНФИГУРАЦИЙ ПК\n"
            f"Обнаружено изменений: {len(notifications)}\n"
            f"Всего устройств с изменениями: {len(pcs_events)}\n"
            f"Время формирования сводки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "=" * 70 + "\n\n"
        )
        
        # Формируем детальную информацию по каждому ПК
        body_parts = []
        for pc_id, events_list in pcs_events.items():
            pc_data = events_list[0][0]  # Берем данные ПК из первого события
            
            # Заголовок для ПК
            location_lines = []
            if pc_data.get('location'):
                location_lines.append(pc_data['location'])
            if pc_data.get('building'):
                location_lines.append(f"Корпус {pc_data['building']}")
            if pc_data.get('floor'):
                location_lines.append(f"Этаж {pc_data['floor']}")
            location_str = " • ".join(location_lines) if location_lines else "не указана"
            
            body_parts.append(
                f"🖥️  ПК: {pc_data['hostname']}\n"
                f"   ID: {pc_data['pc_id']}\n"
                f"   Локация: {location_str}\n"
                f"   Изменений: {len(events_list)}\n"
                "-" * 70
            )
            
            # Детали по каждому изменению
            for idx, (pc_item_data, event_data, event_timestamp) in enumerate(events_list, 1):
                event_type = event_type_ru.get(event_data['event_type'], event_data['event_type'])
                component_type = component_type_ru.get(event_data['component_type'], event_data['component_type'])
                
                # Форматируем время события (используем время из данных события)
                event_time_local = event_data['timestamp']
                if event_time_local:
                    if isinstance(event_time_local, datetime):
                        if event_time_local.tzinfo is None:
                            event_time_local = event_time_local.replace(tzinfo=timezone.utc)
                        local_tz = datetime.now().astimezone().tzinfo
                        event_time_local = event_time_local.astimezone(local_tz)
                        time_str = event_time_local.strftime('%H:%M:%S')
                    else:
                        time_str = str(event_time_local)
                else:
                    time_str = "неизвестно"
                
                body_parts.append(
                    f"\n   [{idx}] {component_type} - {event_type}"
                    f" ({time_str})"
                )
                
                # Детали изменения
                if event_data.get('details'):
                    body_parts.append(f"      Детали: {event_data['details']}")
                
                # Старое значение
                old_value = event_data.get('old_value')
                if old_value and isinstance(old_value, dict):
                    old_model = old_value.get('model') or old_value.get('name') or old_value.get('manufacturer')
                    if old_model:
                        body_parts.append(f"      Было: {old_model}")
                
                # Новое значение
                new_value = event_data.get('new_value')
                if new_value and isinstance(new_value, dict):
                    new_model = new_value.get('model') or new_value.get('name') or new_value.get('manufacturer')
                    if new_model:
                        body_parts.append(f"      Стало: {new_model}")
            
            body_parts.append("\n" + "=" * 70 + "\n")
        
        footer = (
            "\nДля получения подробной информации посетите веб-интерфейс PC-Guardian."
        )
        
        # Формируем финальное сообщение
        return header + "\n".join(body_parts) + footer
    
    @classmethod
    def force_flush_email_buffer(cls):
        """
        Принудительно отправить все накопленные email уведомления
        Полезно вызывать при завершении работы приложения
        """
        if cls._flush_timer and cls._flush_timer.is_alive():
            cls._flush_timer.cancel()
        # Создаем временный экземпляр для вызова метода
        temp_instance = cls()
        temp_instance._flush_email_buffer()




