# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.template.defaultfilters import date
from django.utils.translation import ugettext, ugettext_lazy as _
import datetime
from dateutil import rrule
from schedule.models.rules import Rule
from schedule.models.rooms import Room
from schedule.utils import OccurrenceReplacer

class ReservationManager(models.Manager):

    def get_for_object(self, content_object, distinction=None, inherit=True):
        return ReservationRelation.objects.get_reservations_for_object(content_object, distinction, inherit)

class Reservation(models.Model):
    '''
    This model stores meta data for a date.  You can relate this data to many
    other models.
    '''
    start = models.DateTimeField(_("start"))
    end = models.DateTimeField(_("end"),help_text=_("The end time must be later than the start time."))
    title = models.CharField(_("title"), max_length = 255)
    description = models.TextField(_("description"), null = True, blank = True)
    creator = models.ForeignKey(User, null = True, verbose_name=_("creator"))
    created_on = models.DateTimeField(_("created on"), default = datetime.datetime.now)
    rule = models.ForeignKey(Rule, null = True, blank = True, verbose_name=_("rule"), help_text=_("Select '----' for a one time only reservation."))
    end_recurring_period = models.DateTimeField(_("end recurring period"), null = True, blank = True, help_text=_("This date is ignored for one time only reservations."))
    room = models.ForeignKey(Room, blank=True, null=True)
    objects = ReservationManager()

    class Meta:
        verbose_name = _('reservation')
        verbose_name_plural = _('reservations')
        app_label = 'schedule'
	get_latest_by = 'start' 

    def __unicode__(self):
        date_format = u'l, %s' % ugettext("DATE_FORMAT")
        return ugettext('%(title)s: %(start)s-%(end)s') % {
            'title': self.title,
            'start': date(self.start, date_format),
            'end': date(self.end, date_format),
        }

    def get_absolute_url(self):
        return reverse('reservation', args=[self.id])

    def create_relation(self, obj, distinction = None):
        """
        Creates a ReservationRelation between self and obj.
        """
        ReservationRelation.objects.create_relation(self, obj, distinction)

    def get_occurrences(self, start, end):
        """
        >>> rule = Rule(frequency = "MONTHLY", name = "Monthly")
        >>> rule.save()
        >>> reservation = Reservation(rule=rule, start=datetime.datetime(2008,1,1), end=datetime.datetime(2008,1,2))
        >>> reservation.rule
        <Rule: Monthly>
        >>> occurrences = reservation.get_occurrences(datetime.datetime(2008,1,24), datetime.datetime(2008,3,2))
        >>> ["%s to %s" %(o.start, o.end) for o in occurrences]
        ['2008-02-01 00:00:00 to 2008-02-02 00:00:00', '2008-03-01 00:00:00 to 2008-03-02 00:00:00']

        Ensure that if an reservation has no rule, that it appears only once.

        >>> reservation = Reservation(start=datetime.datetime(2008,1,1,8,0), end=datetime.datetime(2008,1,1,9,0))
        >>> occurrences = reservation.get_occurrences(datetime.datetime(2008,1,24), datetime.datetime(2008,3,2))
        >>> ["%s to %s" %(o.start, o.end) for o in occurrences]
        []

        """
        persisted_occurrences = self.occurrence_set.all()
        occ_replacer = OccurrenceReplacer(persisted_occurrences)
        occurrences = self._get_occurrence_list(start, end)
        final_occurrences = []
        for occ in occurrences:
            # replace occurrences with their persisted counterparts
            if occ_replacer.has_occurrence(occ):
                p_occ = occ_replacer.get_occurrence(
                        occ)
                # ...but only if they are within this period
                if p_occ.start < end and p_occ.end >= start:
                    final_occurrences.append(p_occ)
            else:
              final_occurrences.append(occ)
        # then add persisted occurrences which originated outside of this period but now
        # fall within it
        final_occurrences += occ_replacer.get_additional_occurrences(start, end)
        return final_occurrences

    def get_rrule_object(self):
        if self.rule is not None:
            params = self.rule.get_params()
            frequency = rrule.__dict__[self.rule.frequency]
            return rrule.rrule(frequency, dtstart=self.start, **params)

    def _create_occurrence(self, start, end=None):
        if end is None:
            end = start + (self.end - self.start)
        return Occurrence(reservation=self,start=start,end=end, original_start=start, original_end=end)

    def get_occurrence(self, date):
        rule = self.get_rrule_object()
        if rule:
            next_occurrence = rule.after(date, inc=True)
        else:
            next_occurrence = self.start
        if next_occurrence == date:
            try:
                return Occurrence.objects.get(reservation = self, original_start = date)
            except Occurrence.DoesNotExist:
                return self._create_occurrence(next_occurrence)


    def _get_occurrence_list(self, start, end):
        """
        returns a list of occurrences for this reservation from start to end.
        """
        difference = (self.end - self.start)
        if self.rule is not None:
            occurrences = []
            if self.end_recurring_period and self.end_recurring_period < end:
                end = self.end_recurring_period
            rule = self.get_rrule_object()
            o_starts = rule.between(start-difference, end, inc=False)
            for o_start in o_starts:
                o_end = o_start + difference
                occurrences.append(self._create_occurrence(o_start, o_end))
            return occurrences
        else:
            # check if reservation is in the period
            if self.start < end and self.end >= start:
                return [self._create_occurrence(self.start)]
            else:
                return []

    def _occurrences_after_generator(self, after=None):
        """
        returns a generator that produces unpresisted occurrences after the
        datetime ``after``.
        """

        if after is None:
            after = datetime.datetime.now()
        rule = self.get_rrule_object()
        if rule is None:
            if self.end > after:
                yield self._create_occurrence(self.start, self.end)
            raise StopIteration
        date_iter = iter(rule)
        difference = self.end - self.start
        while True:
            o_start = date_iter.next()
            if o_start > self.end_recurring_period:
                raise StopIteration
            o_end = o_start + difference
            if o_end > after:
                yield self._create_occurrence(o_start, o_end)


    def occurrences_after(self, after=None):
        """
        returns a generator that produces occurrences after the datetime
        ``after``.  Includes all of the persisted Occurrences.
        """
        occ_replacer = OccurrenceReplacer(self.occurrence_set.all())
        generator = self._occurrences_after_generator(after)
        while True:
            next = generator.next()
            yield occ_replacer.get_occurrence(next)
    
    def next_occurrence(self):
        for o in self.occurrences_after():
            return o
    

class ReservationRelationManager(models.Manager):
    '''
    >>> ReservationRelation.objects.all().delete()
    >>> RoomRelation.objects.all().delete()
    >>> data = {
    ...         'title': 'Test1',
    ...         'start': datetime.datetime(2008, 1, 1),
    ...         'end': datetime.datetime(2008, 1, 11)
    ...        }
    >>> Reservation.objects.all().delete()
    >>> reservation1 = Reservation(**data)
    >>> reservation1.save()
    >>> data['title'] = 'Test2'
    >>> reservation2 = Reservation(**data)
    >>> reservation2.save()
    >>> user1 = User(username='alice')
    >>> user1.save()
    >>> user2 = User(username='bob')
    >>> user2.save()
    >>> reservation1.create_relation(user1, 'owner')
    >>> reservation1.create_relation(user2, 'viewer')
    >>> reservation2.create_relation(user1, 'viewer')
    '''
    # Currently not supported
    # Multiple level reverse lookups of generic relations appears to be
    # unsupported in Django, which makes sense.
    #
    # def get_objects_for_reservation(self, reservation, model, distinction=None):
    #     '''
    #     returns a queryset full of instances of model, if it has an ReservationRelation
    #     with reservation, and distinction
    #     >>> reservation = Reservation.objects.get(title='Test1')
    #     >>> ReservationRelation.objects.get_objects_for_reservation(reservation, User, 'owner')
    #     [<User: alice>]
    #     >>> ReservationRelation.objects.get_objects_for_reservation(reservation, User)
    #     [<User: alice>, <User: bob>]
    #     '''
    #     if distinction:
    #         dist_q = Q(reservationrelation__distinction = distinction)
    #     else:
    #         dist_q = Q()
    #     ct = ContentType.objects.get_for_model(model)
    #     return model.objects.filter(
    #         dist_q,
    #         reservationrelation__content_type = ct,
    #         reservationrelation__reservation = reservation
    #     )

    def get_reservations_for_object(self, content_object, distinction=None, inherit=True):
        '''
        returns a queryset full of reservations, that relate to the object through, the
        distinction

        If inherit is false it will not consider the rooms that the reservations
        belong to. If inherit is true it will inherit all of the relations and
        distinctions that any room that it belongs to has, as long as the
        relation has inheritable set to True.  (See Room)

        >>> reservation = Reservation.objects.get(title='Test1')
        >>> user = User.objects.get(username = 'alice')
        >>> ReservationRelation.objects.get_reservations_for_object(user, 'owner', inherit=False)
        [<Reservation: Test1: Tuesday, Jan. 1, 2008-Friday, Jan. 11, 2008>]

        If a distinction is not declared it will not vet the relations based on
        distinction.
        >>> ReservationRelation.objects.get_reservations_for_object(user, inherit=False)
        [<Reservation: Test1: Tuesday, Jan. 1, 2008-Friday, Jan. 11, 2008>, <Reservation: Test2: Tuesday, Jan. 1, 2008-Friday, Jan. 11, 2008>]

        Now if there is a Room
        >>> room = Room(name = 'MyProject')
        >>> room.save()

        And an reservation that belongs to that room
        >>> reservation = Reservation.objects.get(title='Test2')
        >>> room.reservations.add(reservation)

        If we relate this room to some object with inheritable set to true,
        that relation will be inherited
        >>> user = User.objects.get(username='bob')
        >>> cr = room.create_relation(user, 'viewer', True)
        >>> ReservationRelation.objects.get_reservations_for_object(user, 'viewer')
        [<Reservation: Test1: Tuesday, Jan. 1, 2008-Friday, Jan. 11, 2008>, <Reservation: Test2: Tuesday, Jan. 1, 2008-Friday, Jan. 11, 2008>]
        '''
        ct = ContentType.objects.get_for_model(type(content_object))
        if distinction:
            dist_q = Q(reservationrelation__distinction = distinction)
            cal_dist_q = Q(room__roomrelation__distinction = distinction)
        else:
            dist_q = Q()
            cal_dist_q = Q()
        if inherit:
            inherit_q = Q(
                cal_dist_q,
                room__roomrelation__object_id = content_object.id,
                room__roomrelation__content_type = ct,
                room__roomrelation__inheritable = True,
            )
        else:
            inherit_q = Q()
        reservation_q = Q(dist_q, Q(reservationrelation__object_id=content_object.id),Q(reservationrelation__content_type=ct))
        return Reservation.objects.filter(inherit_q|reservation_q)

    def change_distinction(self, distinction, new_distinction):
        '''
        This function is for change the a group of reservationrelations from an old
        distinction to a new one. It should only be used for managerial stuff.
        It is also expensive so it should be used sparingly.
        '''
        for relation in self.filter(distinction = distinction):
            relation.distinction = new_distinction
            relation.save()

    def create_relation(self, reservation, content_object, distinction=None):
        """
        Creates a relation between reservation and content_object.
        See ReservationRelation for help on distinction.
        """
        ct = ContentType.objects.get_for_model(type(content_object))
        object_id = content_object.id
        er = ReservationRelation(
            content_type = ct,
            object_id = object_id,
            reservation = reservation,
            distinction = distinction,
            content_object = content_object
        )
        er.save()
        return er


class ReservationRelation(models.Model):
    '''
    This is for relating data to an Reservation, there is also a distinction, so that
    data can be related in different ways.  A good example would be, if you have
    reservations that are only visible by certain users, you could create a relation
    between reservations and users, with the distinction of 'visibility', or
    'ownership'.

    reservation: a foreign key relation to an Reservation model.
    content_type: a foreign key relation to ContentType of the generic object
    object_id: the id of the generic object
    content_object: the generic foreign key to the generic object
    distinction: a string representing a distinction of the relation, User could
    have a 'veiwer' relation and an 'owner' relation for example.

    DISCLAIMER: while this model is a nice out of the box feature to have, it
    may not scale well.  If you use this keep that in mindself.
    '''
    reservation = models.ForeignKey(Reservation, verbose_name=_("reservation"))
    content_type = models.ForeignKey(ContentType)
    object_id = models.IntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    distinction = models.CharField(_("distinction"), max_length = 20, null=True)

    objects = ReservationRelationManager()

    class Meta:
        verbose_name = _("reservation relation")
        verbose_name_plural = _("reservation relations")
        app_label = 'schedule'

    def __unicode__(self):
        return u'%s(%s)-%s' % (self.reservation.title, self.distinction, self.content_object)




class Occurrence(models.Model):
    reservation = models.ForeignKey(Reservation, verbose_name=_("reservation"))
    title = models.CharField(_("title"), max_length=255, blank=True, null=True)
    description = models.TextField(_("description"), blank=True, null=True)
    start = models.DateTimeField(_("start"))
    end = models.DateTimeField(_("end"))
    cancelled = models.BooleanField(_("cancelled"), default=False)
    original_start = models.DateTimeField(_("original start"))
    original_end = models.DateTimeField(_("original end"))

    class Meta:
        verbose_name = _("occurrence")
        verbose_name_plural = _("occurrences")
        app_label = 'schedule'

    def __init__(self, *args, **kwargs):
        super(Occurrence, self).__init__(*args, **kwargs)
        if self.title is None:
            self.title = self.reservation.title
        if self.description is None:
            self.description = self.reservation.description


    def moved(self):
        return self.original_start != self.start or self.original_end != self.end
    moved = property(moved)

    def move(self, new_start, new_end):
        self.start = new_start
        self.end = new_end
        self.save()

    def cancel(self):
        self.cancelled = True
        self.save()

    def uncancel(self):
        self.cancelled = False
        self.save()

    def get_absolute_url(self):
        if self.pk is not None:
            return reverse('occurrence', kwargs={'occurrence_id': self.pk,
                'reservation_id': self.reservation.id})
        return reverse('occurrence_by_date', kwargs={
            'reservation_id': self.reservation.id,
            'year': self.start.year,
            'month': self.start.month,
            'day': self.start.day,
            'hour': self.start.hour,
            'minute': self.start.minute,
            'second': self.start.second,
        })

    def get_cancel_url(self):
        if self.pk is not None:
            return reverse('cancel_occurrence', kwargs={'occurrence_id': self.pk,
                'reservation_id': self.reservation.id})
        return reverse('cancel_occurrence_by_date', kwargs={
            'reservation_id': self.reservation.id,
            'year': self.start.year,
            'month': self.start.month,
            'day': self.start.day,
            'hour': self.start.hour,
            'minute': self.start.minute,
            'second': self.start.second,
        })

    def get_edit_url(self):
        if self.pk is not None:
            return reverse('edit_occurrence', kwargs={'occurrence_id': self.pk,
                'reservation_id': self.reservation.id})
        return reverse('edit_occurrence_by_date', kwargs={
            'reservation_id': self.reservation.id,
            'year': self.start.year,
            'month': self.start.month,
            'day': self.start.day,
            'hour': self.start.hour,
            'minute': self.start.minute,
            'second': self.start.second,
        })

    def __unicode__(self):
        return ugettext("%(start)s to %(end)s") % {
            'start': self.start,
            'end': self.end,
        }

    def __cmp__(self, other):
        rank = cmp(self.start, other.start)
        if rank == 0:
            return cmp(self.end, other.end)
        return rank

    def __eq__(self, other):
        return self.reservation == other.reservation and self.original_start == other.original_start and self.original_end == other.original_end
