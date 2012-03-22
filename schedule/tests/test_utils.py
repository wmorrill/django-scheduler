import datetime
import os

from django.test import TestCase
from django.core.urlresolvers import reverse

from schedule.models import Reservation, Rule, Occurrence, Room
from schedule.periods import Period, Month, Day
from schedule.utils import ReservationListManager

class TestReservationListManager(TestCase):
    def setUp(self):
        weekly = Rule(frequency = "WEEKLY")
        weekly.save()
        daily = Rule(frequency = "DAILY")
        daily.save()
        cal = Room(name="MyCal")
        cal.save()

        self.reservation1 = Reservation(**{
                'title': 'Weekly Reservation',
                'start': datetime.datetime(2009, 4, 1, 8, 0),
                'end': datetime.datetime(2009, 4, 1, 9, 0),
                'end_recurring_period' : datetime.datetime(2009, 10, 5, 0, 0),
                'rule': weekly,
                'room': cal
               })
        self.reservation1.save()
        self.reservation2 = Reservation(**{
                'title': 'Recent Reservation',
                'start': datetime.datetime(2008, 1, 5, 9, 0),
                'end': datetime.datetime(2008, 1, 5, 10, 0),
                'end_recurring_period' : datetime.datetime(2009, 5, 5, 0, 0),
                'rule': daily,
                'room': cal
               })
        self.reservation2.save()

    def test_occurrences_after(self):
        eml = ReservationListManager([self.reservation1, self.reservation2])
        occurrences = eml.occurrences_after(datetime.datetime(2009,4,1,0,0))
        self.assertEqual(occurrences.next().reservation, self.reservation1)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation2)
        self.assertEqual(occurrences.next().reservation, self.reservation1)
