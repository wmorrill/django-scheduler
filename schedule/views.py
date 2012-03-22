from urllib import quote
from django.shortcuts import render_to_response, get_object_or_404
from django.views.generic.create_update import delete_object
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.generic.create_update import delete_object
import datetime

from schedule.conf.settings import GET_EVENTS_FUNC, OCCURRENCE_CANCEL_REDIRECT
from schedule.forms import ReservationForm, OccurrenceForm
from schedule.models import *
from schedule.periods import weekday_names
from schedule.utils import check_reservation_permissions, coerce_date_dict

def room(request, room_slug, template='schedule/room.html', extra_context=None):
    """
    This view returns a room.  This view should be used if you are
    interested in the meta data of a room, not if you want to display a
    room.  It is suggested that you use room_by_periods if you would
    like to display a room.

    Context Variables:

    ``room``
        The Room object designated by the ``room_slug``.
    """
    extra_context = extra_context or {}
    room = get_object_or_404(Room, slug=room_slug)
    context = {"room": room}
    context.update(extra_context)
    return render_to_response(template, context, context_instance=RequestContext(request))

def room_by_periods(request, room_slug, periods=None,
    template_name="schedule/room_by_period.html", extra_context=None):
    """
    This view is for getting a room, but also getting periods with that
    room.  Which periods you get, is designated with the list periods. You
    can designate which date you the periods to be initialized to by passing
    a date in request.GET. See the template tag ``query_string_for_date``

    Context Variables

    ``date``
        This was the date that was generated from the query string.

    ``periods``
        this is a dictionary that returns the periods from the list you passed
        in.  If you passed in Month and Day, then your dictionary would look
        like this

        {
            'month': <schedule.periods.Month object>
            'day':   <schedule.periods.Day object>
        }

        So in the template to access the Day period in the context you simply
        use ``periods.day``.

    ``room``
        This is the Room that is designated by the ``room_slug``.

    ``weekday_names``
        This is for convenience. It returns the local names of weekedays for
        internationalization.

    """
    extra_context = extra_context or {}
    room = get_object_or_404(Room, slug=room_slug)
    date = coerce_date_dict(request.GET)
    if date:
        try:
            date = datetime.datetime(**date)
        except ValueError:
            raise Http404
    else:
        date = datetime.datetime.now()
    reservation_list = GET_EVENTS_FUNC(request, room)
    period_objects = dict([(period.__name__.lower(), period(reservation_list, date)) for period in periods])
    context = {
            'date': date,
            'periods': period_objects,
            'room': room,
            'weekday_names': weekday_names,
            'here':quote(request.get_full_path()),
        }
    context.update(extra_context)
    return render_to_response(template_name, context, context_instance=RequestContext(request),)

def reservation(request, reservation_id, template_name="schedule/reservation.html", extra_context=None):
    """
    This view is for showing an reservation. It is important to remember that an
    reservation is not an occurrence.  Reservations define a set of reccurring occurrences.
    If you would like to display an occurrence (a single instance of a
    recurring reservation) use occurrence.

    Context Variables:

    reservation
        This is the reservation designated by the reservation_id

    back_url
        this is the url that referred to this view.
    """
    extra_context = extra_context or {}
    reservation = get_object_or_404(Reservation, id=reservation_id)
    back_url = request.META.get('HTTP_REFERER', None)
    try:
        cal = reservation.room_set.get()
    except:
        cal = None
    context = {
        "reservation": reservation,
        "back_url" : back_url,
    }
    context.update(extra_context)
    return render_to_response(template_name, context, context_instance=RequestContext(request))

def occurrence(request, reservation_id,
    template_name="schedule/occurrence.html", *args, **kwargs):
    """
    This view is used to display an occurrence.

    Context Variables:

    ``reservation``
        the reservation that produces the occurrence

    ``occurrence``
        the occurrence to be displayed

    ``back_url``
        the url from which this request was refered
    """
    extra_context = kwargs.get('extra_context', None) or {}
    reservation, occurrence = get_occurrence(reservation_id, *args, **kwargs)
    back_url = request.META.get('HTTP_REFERER', None)
    context =  {
        'reservation': reservation,
        'occurrence': occurrence,
        'back_url': back_url,
    }
    context.update(extra_context)
    return render_to_response(template_name, context, context_instance=RequestContext(request))


@check_reservation_permissions
def edit_occurrence(request, reservation_id,
    template_name="schedule/edit_occurrence.html", *args, **kwargs):
    extra_context = kwargs.get('extra_context', None) or {}
    reservation, occurrence = get_occurrence(reservation_id, *args, **kwargs)
    next = kwargs.get('next', None)
    form = OccurrenceForm(data=request.POST or None, instance=occurrence)
    if form.is_valid():
        occurrence = form.save(commit=False)
        occurrence.reservation = reservation
        occurrence.save()
        next = next or get_next_url(request, occurrence.get_absolute_url())
        return HttpResponseRedirect(next)
    next = next or get_next_url(request, occurrence.get_absolute_url())
    context = {
        'form': form,
        'occurrence': occurrence,
        'next':next,
    }
    context.update(extra_context)
    return render_to_response(template_name, context, context_instance=RequestContext(request))


@check_reservation_permissions
def cancel_occurrence(request, reservation_id,
    template_name='schedule/cancel_occurrence.html', *args, **kwargs):
    """
    This view is used to cancel an occurrence. If it is called with a POST it
    will cancel the view. If it is called with a GET it will ask for
    conformation to cancel.
    """
    extra_context = kwargs.get('extra_context', None) or {}
    reservation, occurrence = get_occurrence(reservation_id, *args, **kwargs)
    next = kwargs.get('next',None) or get_next_url(request, reservation.get_absolute_url())
    if request.method != "POST":
        context = {
            "occurrence": occurrence,
            "next":next,
        }
        context.update(extra_context)
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    occurrence.cancel()
    return HttpResponseRedirect(next)


def get_occurrence(reservation_id, occurrence_id=None, year=None, month=None,
    day=None, hour=None, minute=None, second=None):
    """
    Because occurrences don't have to be persisted, there must be two ways to
    retrieve them. both need an reservation, but if its persisted the occurrence can
    be retrieved with an id. If it is not persisted it takes a date to
    retrieve it.  This function returns an reservation and occurrence regardless of
    which method is used.
    """
    if(occurrence_id):
        occurrence = get_object_or_404(Occurrence, id=occurrence_id)
        reservation = occurrence.reservation
    elif(all((year, month, day, hour, minute, second))):
        reservation = get_object_or_404(Reservation, id=reservation_id)
        occurrence = reservation.get_occurrence(
            datetime.datetime(int(year), int(month), int(day), int(hour),
                int(minute), int(second)))
        if occurrence is None:
            raise Http404
    else:
        raise Http404
    return reservation, occurrence


@check_reservation_permissions
def create_or_edit_reservation(request, room_slug, reservation_id=None, next=None,
    template_name='schedule/create_reservation.html', form_class = ReservationForm, extra_context=None):
    """
    This function, if it receives a GET request or if given an invalid form in a
    POST request it will generate the following response

    Template:
        schedule/create_reservation.html

    Context Variables:

    form:
        an instance of ReservationForm

    room:
        a Room with id=room_id

    if this function gets a GET request with ``year``, ``month``, ``day``,
    ``hour``, ``minute``, and ``second`` it will auto fill the form, with
    the date specifed in the GET being the start and 30 minutes from that
    being the end.

    If this form receives an reservation_id it will edit the reservation with that id, if it
    recieves a room_id and it is creating a new reservation it will add that reservation
    to the room with the id room_id

    If it is given a valid form in a POST request it will redirect with one of
    three options, in this order

    # Try to find a 'next' GET variable
    # If the key word argument redirect is set
    # Lastly redirect to the reservation detail of the recently create reservation
    """
    extra_context = extra_context or {}
    date = coerce_date_dict(request.GET)
    initial_data = None
    if date:
        try:
            start = datetime.datetime(**date)
            initial_data = {
                "start": start,
                "end": start + datetime.timedelta(minutes=30)
            }
        except TypeError:
            raise Http404
        except ValueError:
            raise Http404

    instance = None
    if reservation_id is not None:
        instance = get_object_or_404(Reservation, id=reservation_id)

    room = get_object_or_404(Room, slug=room_slug)

    form = form_class(data=request.POST or None, instance=instance,
        hour24=True, initial=initial_data)

    if form.is_valid():
        reservation = form.save(commit=False)
        if instance is None:
            reservation.creator = request.user
            reservation.room = room
        reservation.save()
        next = next or reverse('reservation', args=[reservation.id])
        next = get_next_url(request, next)
        return HttpResponseRedirect(next)

    next = get_next_url(request, next)
    context = {
        "form": form,
        "room": room,
        "next":next
    }
    context.update(extra_context)
    return render_to_response(template_name, context, context_instance=RequestContext(request))


@check_reservation_permissions
def delete_reservation(request, reservation_id, next=None, login_required=True, extra_context=None):
    """
    After the reservation is deleted there are three options for redirect, tried in
    this order:

    # Try to find a 'next' GET variable
    # If the key word argument redirect is set
    # Lastly redirect to the reservation detail of the recently create reservation
    """
    extra_context = extra_context or {}
    reservation = get_object_or_404(Reservation, id=reservation_id)
    next = next or reverse('day_room', args=[reservation.room.slug])
    next = get_next_url(request, next)
    extra_context['next'] = next
    return delete_object(request,
                         model = Reservation,
                         object_id = reservation_id,
                         post_delete_redirect = next,
                         template_name = "schedule/delete_reservation.html",
                         extra_context = extra_context,
                         login_required = login_required
                        )

def check_next_url(next):
    """
    Checks to make sure the next url is not redirecting to another page.
    Basically it is a minimal security check.
    """
    if not next or '://' in next:
        return None
    return next

def get_next_url(request, default):
    next = default
    if OCCURRENCE_CANCEL_REDIRECT:
        next = OCCURRENCE_CANCEL_REDIRECT
    if 'next' in request.REQUEST and check_next_url(request.REQUEST['next']) is not None:
        next = request.REQUEST['next']
    return next
