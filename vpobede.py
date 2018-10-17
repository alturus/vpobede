import json
import datetime
import requests
from os import mkdir
from os.path import join, dirname, isdir, abspath


class Vpobede(object):

    VPOBEDE_URL = "https://vpobede.ru/"
    VPOBEDE_API_URL = 'https://vpobede.ru/backend/api/'

    CACHE_DIR = 'cache'
    CACHE_FILENAME = 'events.json'

    DEFAULT_CACHE_TTL = 86400     # Максимальное время хранения в кэше в секундах
    DEFAULT_SCHEDULE_PERIOD = 31  # Получение событий за указанный период в днях

    DEFAULT_EVENTS_LIMIT = 0      # Лимит загружаемых событий. 0 - без лимита

    def __init__(self):
        self.cache_file_path = join(dirname(abspath(__file__)), self.CACHE_DIR, self.CACHE_FILENAME)
        self.events = {
            'update_datetime': datetime.datetime(2012, 1, 1, 0, 0, 0),
            'events': {},
            'groups': {},
        }

    def get_url(self):
        """Ссылка на сайт кинотеатра"""
        return self.VPOBEDE_URL

    def save_to_cache(self):
        """Сохраняет данные в JSON-файл кэша"""
        data_to_save = self.events.copy()
        data_to_save['update_datetime'] = self.events['update_datetime'].isoformat()
        try:
            dir_path = dirname(self.cache_file_path)
            if dir_path and not isdir(dir_path):
                mkdir(dir_path)

            with open(self.cache_file_path, 'w', encoding='utf-8') as json_file:
                json.dump(data_to_save, json_file, ensure_ascii=False)
        except IOError:
            return False

        return True

    def load_from_cache(self, cache_ttl=DEFAULT_CACHE_TTL):
        """Загружает данные из JSON-файла кэша"""
        try:
            with open(self.cache_file_path, 'r') as json_file:
                data = json.load(json_file)
        except Exception:
            return False

        if not data:
            return False

        # Проверяем актуальность данных в кэше
        today = datetime.datetime.today()
        update_datetime = datetime.datetime.strptime(data['update_datetime'], "%Y-%m-%dT%H:%M:%S.%f")
        data['update_datetime'] = update_datetime

        cache_age = today - update_datetime

        if cache_age.total_seconds() > cache_ttl:
            return False  # Кэш просрочен

        self.events = data

        return True

    @staticmethod
    def get_http(url):
        """Получение данных с сайта по указанному URL"""
        try:
            http_response = requests.get(url)
            if http_response.status_code == requests.codes.ok:
                data = http_response.json()
            else:
                data = None
        except requests.exceptions.RequestException:
            return None

        return data

    def get_event_details(self, event_id):
        """Получение с сайта дополнительной информации о событии"""
        event_url = self.VPOBEDE_API_URL + f'event/events/{event_id}?_scope=ext_view'
        event_data = self.get_http(event_url)

        if not event_data:
            return None

        event_details = {
            'year': event_data['techParameters'][0]['value'],        # Год выхода
            'country': event_data['techParameters'][1]['value'],     # Страна производитель
            'director': event_data['techParameters'][2]['value'],    # Режиссёр
            'lead': event_data['lead'],                              # Слоган события
            'description': event_data['body'],                       # Описание события
            'slug': event_data['slug'],                              # slug для формирование url на событие
            'age_restriction': event_data['ageRestriction'],         # Возрастное ограничение
            'duration': event_data['duration'],                      # Длительность в минутах
            'session_only_here': event_data.get('sessionOnlyHere'),  # Событие проходит только в Победе
            'session_baby': event_data.get('sessionBaby'),           # Событие для детей
            'performance': {                                         # Словарь с перечнем характеристик сеансов
                'sessionSubtitles': False,                           # На языке оригинала с субтитрами
                'session2d': False,                                  # В 2D
                'session3d': False,                                  # В 3D
                'session4k': False,                                  # В 4K
                'session48fps': False,                               # С 48 fps
                'sessionAutismFriendly': False,                      # Подходит для людей с аутизмом
            },
        }

        for performance in event_data['performances']:
            for key, value in performance.items():
                if str(key).startswith('session') and value is True:
                    event_details['performance'][key] = True

        return event_details

    def get_event_sessions(self, event_id):
        """
        Получает перечень будующих сеансов для события

        Возвращает:
            event_sessions - Список дат и времени всех сеансов
            event_sessions_days - Список дней, когда есть сеансы в формате 'ДД/ММ'
        """
        event_sessions_url = self.VPOBEDE_API_URL + f'event/sessions?event={event_id}'
        event_sessions_data = self.get_http(event_sessions_url)

        event_sessions = []
        event_sessions_days = set()

        for session in event_sessions_data:
            start_datetime = datetime.datetime.strptime(session['startTime'][:-6], '%Y-%m-%dT%H:%M:%S')
            if start_datetime > datetime.datetime.today():
                event_sessions.append(session['startTime'])
                event_sessions_days.add(datetime.datetime.strftime(start_datetime, '%d/%m'))

        event_sessions_days = sorted(list(event_sessions_days))

        return event_sessions, event_sessions_days

    def update_events(self, schedule_period=DEFAULT_SCHEDULE_PERIOD, events_limit=DEFAULT_EVENTS_LIMIT, save_to_cache=True):
        """Обновляет события с сайта кинотеатра"""
        start_time = 'NOW'
        end_time = datetime.datetime.today() + datetime.timedelta(days=schedule_period)
        end_time = end_time.strftime('%Y-%m-%dT04:00:00') + '%2B07:00'

        limit = ''
        if events_limit > 0:
            limit = f'_limit={events_limit}&'

        events_url = (self.VPOBEDE_API_URL +
                      f'event/events?{limit}_offset=0&_sort[session]=asc&endTime={end_time}&startTime={start_time}')

        events = {}
        events_groups = {
            '9999': {           # События без группы сохраняются в группу 9999
                'name': '',     # Наименование группы событий
                'events': [],   # Перечень ID событий входящих в группу
            },
        }

        vpobede_events = self.get_http(events_url)

        if not vpobede_events:
            return False

        for vpobede_event in vpobede_events:
            event_id = str(vpobede_event['id'])
            event_name = vpobede_event['name']
            event_name_eng = vpobede_event['nameEng']
            event_billboard_url = vpobede_event['billboardThumbnails'].get('event_billboard_320')
            event_genres = [genre.get('name') for genre in vpobede_event['genres']]

            events[event_id] = {
                'name': event_name,                    # Наименование события/фильма
                'name_eng': event_name_eng,            # Наименование на английском языке
                'billboard_url': event_billboard_url,  # Ссылка на изображение постера
                'genres': event_genres,                # Перечень жанров к которым относится событие
            }

            event_details = self.get_event_details(int(event_id))  # Получаем с сайта доп.информацию о событии
            event_sessions, event_sessions_days = self.get_event_sessions(
                int(event_id))  # Сеансы и дни, когда проходит событие

            events[event_id].update(event_details)
            events[event_id].update({
                'sessions': event_sessions,
                'sessions_days': event_sessions_days,
            })

            # Получаем все группы событий
            event_group_id = '9999'  # Группа по-умолчанию (все события без группы попадают сюда)
            event_group_name = ''

            if vpobede_event['eventGroup']:
                event_group_id = str(vpobede_event['eventGroup']['id'])
                if vpobede_event['eventGroup']['currentSet']:
                    event_group_name = vpobede_event['eventGroup']['currentSet'].get('name')
                else:
                    event_group_name = vpobede_event['eventGroup'].get('name')

            if event_group_id in events_groups:
                events_groups[event_group_id]['events'].append(event_id)
            else:
                events_groups[event_group_id] = {
                    'name': event_group_name,
                    'events': [event_id, ],
                }

        self.events.update({
            'update_datetime': datetime.datetime.today(),
            'events': events,
            'groups': events_groups,
        })

        if save_to_cache:
            self.save_to_cache()

        return True

    def get_events(self, use_cache=True, cache_ttl=DEFAULT_CACHE_TTL):
        """Обновляет данные по событиям и возвращает словарь с событиями/фильмами"""

        if use_cache:
            # Проверяем свежесть имеющихся данных. Если свежие - отдаём их.
            if self.events.get('update_datetime'):
                if (datetime.datetime.today() - self.events['update_datetime']).total_seconds() < cache_ttl:
                    return self.events

            # Загружаем данные из кэша
            if self.load_from_cache(cache_ttl):
                return self.events

        self.update_events()  # Обновляем события с сайта кинотеатра, т.к. в кэше нет свежих данных

        return self.events
