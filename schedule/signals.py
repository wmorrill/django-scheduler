from django.db.models.signals import pre_save

from models import Reservation, Room

def optionnal_room(sender, **kwargs):
    reservation = kwargs.pop('instance')
        
    if not isinstance(reservation, Reservation):
        return True
    if not reservation.room:
        try:
            room = Room._default_manager.get(name='default')
        except Room.DoesNotExist:
            room = Room(name='default', slug='default')
            room.save()

        reservation.room = room
    return True

pre_save.connect(optionnal_room)
