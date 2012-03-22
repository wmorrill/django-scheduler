from django.utils.translation import ugettext, ugettext_lazy as _
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

fdow_default = 0 # Sunday

# Look for FIRST_DAY_OF_WEEK as a locale setting
fdow = ugettext('FIRST_DAY_OF_WEEK')
try:
    FIRST_DAY_OF_WEEK = int(fdow)
except ValueError:
    # Let's try our settings
    fdow = getattr(settings, 'FIRST_DAY_OF_WEEK', fdow_default)
    FIRST_DAY_OF_WEEK = int(fdow)
except ValueError:
    raise ImproperlyConfigured("FIRST_DAY_OF_WEEK must be an integer between 0 and 6")


# whether to display cancelled occurrences
# (if they are displayed then they have a css class "cancelled")
# this controls behaviour of Period.classify_occurrence method
SHOW_CANCELLED_OCCURRENCES = getattr(settings, 'SHOW_CANCELLED_OCCURRENCES',
                                     False)

# Callable used to check if a user has edit permissions to reservation
# (and occurrence). Used by check_edit_permission decorator
# if ob==None we check permission to add occurrence
CHECK_PERMISSION_FUNC = getattr(settings, 'CHECK_PERMISSION_FUNC', None)
if not CHECK_PERMISSION_FUNC:
    def check_edit_permission(ob, user):
        return user.is_authenticated()

    CHECK_PERMISSION_FUNC = check_edit_permission

# Callable used to customize the reservation list given for a room and user
# (e.g. all reservations on that room, those reservations plus another room's reservations,
# or the reservations filtered based on user permissions)
# Imports have to be placed within the function body to avoid circular imports
GET_EVENTS_FUNC = getattr(settings, 'GET_EVENTS_FUNC', None)
if not GET_EVENTS_FUNC:
    def get_reservations(request, room):
        return room.reservation_set.all()

    GET_EVENTS_FUNC = get_reservations

# URL to redirect to to after an occurrence is canceled
OCCURRENCE_CANCEL_REDIRECT = getattr(settings, 'OCCURRENCE_CANCEL_REDIRECT', None)
