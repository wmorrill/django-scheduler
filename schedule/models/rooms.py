# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext, ugettext_lazy as _
from django.template.defaultfilters import slugify
import datetime
from dateutil import rrule
from schedule.utils import ReservationListManager

class RoomManager(models.Manager):
    """
    >>> user1 = User(username='tony')
    >>> user1.save()
    """
    def get_room_for_object(self, obj, distinction=None):
        """
        This function gets a room for an object.  It should only return one
        room.  If the object has more than one room related to it (or
        more than one related to it under a distinction if a distinction is
        defined) an AssertionError will be raised.  If none are returned it will
        raise a DoesNotExistError.

        >>> user = User.objects.get(username='tony')
        >>> try:
        ...     Room.objects.get_room_for_object(user)
        ... except Room.DoesNotExist:
        ...     print "failed"
        ...
        failed

        Now if we add a room it should return the room

        >>> room = Room(name='My Cal')
        >>> room.save()
        >>> room.create_relation(user)
        >>> Room.objects.get_room_for_object(user)
        <Room: My Cal>

        Now if we add one more room it should raise an AssertionError
        because there is more than one related to it.

        If you would like to get more than one room for an object you should
        use get_rooms_for_object (see below).
        >>> room = Room(name='My 2nd Cal')
        >>> room.save()
        >>> room.create_relation(user)
        >>> try:
        ...     Room.objects.get_room_for_object(user)
        ... except AssertionError:
        ...     print "failed"
        ...
        failed
        """
        room_list = self.get_rooms_for_object(obj, distinction)
        if len(room_list) == 0:
            raise Room.DoesNotExist, "Room does not exist."
        elif len(room_list) > 1:
            raise AssertionError, "More than one rooms were found."
        else:
            return room_list[0]

    def get_or_create_room_for_object(self, obj, distinction = None, name = None):
        """
        >>> user = User(username="jeremy")
        >>> user.save()
        >>> room = Room.objects.get_or_create_room_for_object(user, name = "Jeremy's Room")
        >>> room.name
        "Jeremy's Room"
        """
        try:
            return self.get_room_for_object(obj, distinction)
        except Room.DoesNotExist:
            if name is None:
                room = Room(name = unicode(obj))
            else:
                room = Room(name = name)
            room.slug = slugify(room.name)
            room.save()
            room.create_relation(obj, distinction)
            return room

    def get_rooms_for_object(self, obj, distinction = None):
        """
        This function allows you to get rooms for a specific object

        If distinction is set it will filter out any relation that doesnt have
        that distinction.
        """
        ct = ContentType.objects.get_for_model(type(obj))
        if distinction:
            dist_q = Q(roomrelation__distinction=distinction)
        else:
            dist_q = Q()
        return self.filter(dist_q, Q(roomrelation__object_id=obj.id, roomrelation__content_type=ct))

class Room(models.Model):
    '''
    This is for grouping reservations so that batch relations can be made to all
    reservations.  An example would be a project room.

    name: the name of the room
    reservations: all the reservations contained within the room.
    >>> room = Room(name = 'Test Room')
    >>> room.save()
    >>> data = {
    ...         'title': 'Recent Reservation',
    ...         'start': datetime.datetime(2008, 1, 5, 0, 0),
    ...         'end': datetime.datetime(2008, 1, 10, 0, 0)
    ...        }
    >>> reservation = Reservation(**data)
    >>> reservation.save()
    >>> room.reservations.add(reservation)
    >>> data = {
    ...         'title': 'Upcoming Reservation',
    ...         'start': datetime.datetime(2008, 1, 1, 0, 0),
    ...         'end': datetime.datetime(2008, 1, 4, 0, 0)
    ...        }
    >>> reservation = Reservation(**data)
    >>> reservation.save()
    >>> room.reservations.add(reservation)
    >>> data = {
    ...         'title': 'Current Reservation',
    ...         'start': datetime.datetime(2008, 1, 3),
    ...         'end': datetime.datetime(2008, 1, 6)
    ...        }
    >>> reservation = Reservation(**data)
    >>> reservation.save()
    >>> room.reservations.add(reservation)
    '''

    name = models.CharField(_("name"), max_length = 200)
    slug = models.SlugField(_("slug"),max_length = 200)
    objects = RoomManager()

    class Meta:
        verbose_name = _('room')
        verbose_name_plural = _('room')
        app_label = 'schedule'

    def __unicode__(self):
        return self.name

    def reservations(self):
        return self.reservation_set.all()
    reservations = property(reservations)

    def create_relation(self, obj, distinction = None, inheritable = True):
        """
        Creates a RoomRelation between self and obj.

        if Inheritable is set to true this relation will cascade to all reservations
        related to this room.
        """
        RoomRelation.objects.create_relation(self, obj, distinction, inheritable)

    def get_recent(self, amount=5, in_datetime = datetime.datetime.now):
        """
        This shortcut function allows you to get reservations that have started
        recently.

        amount is the amount of reservations you want in the queryset. The default is
        5.

        in_datetime is the datetime you want to check against.  It defaults to
        datetime.datetime.now
        """
        return self.reservations.order_by('-start').filter(start__lt=datetime.datetime.now())[:amount]

    def occurrences_after(self, date=None):
        return ReservationListManager(self.reservations.all()).occurrences_after(date)

    def get_absolute_url(self):
        return reverse('room_home', kwargs={'room_slug':self.slug})

    def add_reservation_url(self):
        return reverse('s_create_reservation_in_room', args=[self.slug])


class RoomRelationManager(models.Manager):
    def create_relation(self, room, content_object, distinction=None, inheritable=True):
        """
        Creates a relation between room and content_object.
        See RoomRelation for help on distinction and inheritable
        """
        ct = ContentType.objects.get_for_model(type(content_object))
        object_id = content_object.id
        cr = RoomRelation(
            content_type = ct,
            object_id = object_id,
            room = room,
            distinction = distinction,
            content_object = content_object
        )
        cr.save()
        return cr

class RoomRelation(models.Model):
    '''
    This is for relating data to a Room, and possible all of the reservations for
    that room, there is also a distinction, so that the same type or kind of
    data can be related in different ways.  A good example would be, if you have
    rooms that are only visible by certain users, you could create a
    relation between rooms and users, with the distinction of 'visibility',
    or 'ownership'.  If inheritable is set to true, all the reservations for this
    room will inherit this relation.

    room: a foreign key relation to a Room object.
    content_type: a foreign key relation to ContentType of the generic object
    object_id: the id of the generic object
    content_object: the generic foreign key to the generic object
    distinction: a string representing a distinction of the relation, User could
    have a 'veiwer' relation and an 'owner' relation for example.
    inheritable: a boolean that decides if reservations of the room should also
    inherit this relation

    DISCLAIMER: while this model is a nice out of the box feature to have, it
    may not scale well.  If you use this, keep that in mind.
    '''

    room = models.ForeignKey(Room, verbose_name=_("room"))
    content_type = models.ForeignKey(ContentType)
    object_id = models.IntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    distinction = models.CharField(_("distinction"), max_length = 20, null=True)
    inheritable = models.BooleanField(_("inheritable"), default=True)

    objects = RoomRelationManager()

    class Meta:
        verbose_name = _('room relation')
        verbose_name_plural = _('room relations')
        app_label = 'schedule'

    def __unicode__(self):
        return u'%s - %s' %(self.room, self.content_object)
