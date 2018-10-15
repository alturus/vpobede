from flask import render_template
from vpobede import Vpobede
from . import main


@main.route('/vpobede/')
def index():
    vpobede = Vpobede()
    events = vpobede.get_events(cache_ttl=46800)
    content = {
        'update_datetime': events['update_datetime'].strftime("%Y-%m-%d %H:%M:%S"),
        'events': events['events'],
        'events_count': len(events['events']),
        'event_groups': events['groups'],
        'vpobede_url': vpobede.get_url(),
    }
    return render_template('index.html', **content)
