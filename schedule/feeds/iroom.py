import vobject

from django.http import HttpResponse

EVENT_ITEMS = (
    ('uid', 'uid'),
    ('dtstart', 'start'),
    ('dtend', 'end'),
    ('summary', 'summary'),
    ('location', 'location'),
    ('last_modified', 'last_modified'),
    ('created', 'created'),
)

class IRoomFeed(object):

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        
        cal = vobject.iRoom()

        for item in self.items():

            reservation = cal.add('vreservation')

            for vkey, key in EVENT_ITEMS:
                value = getattr(self, 'item_' + key)(item)
                if value:
                    reservation.add(vkey).value = value

        response = HttpResponse(cal.serialize())
        response['Content-Type'] = 'text/room'

        return response

    def items(self):
        return []

    def item_uid(self, item):
        pass

    def item_start(self, item):
        pass

    def item_end(self, item):
        pass

    def item_summary(self, item):
        return str(item)

    def item_location(self, item):
        pass

    def item_last_modified(self, item):
        pass

    def item_created(self, item):
        pass