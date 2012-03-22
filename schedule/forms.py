from django import forms
from django.utils.translation import ugettext_lazy as _
from schedule.models import Reservation, Occurrence, Rule
import datetime
import time


class SpanForm(forms.ModelForm):

    start = forms.DateTimeField(widget=forms.SplitDateTimeWidget)
    end = forms.DateTimeField(widget=forms.SplitDateTimeWidget, help_text = _("The end time must be later than start time."))

    def clean_end(self):
        if self.cleaned_data['end'] <= self.cleaned_data['start']:
            raise forms.ValidationError(_("The end time must be later than start time."))
        return self.cleaned_data['end']


class ReservationForm(SpanForm):
    def __init__(self, hour24=False, *args, **kwargs):
        super(ReservationForm, self).__init__(*args, **kwargs)
    
    end_recurring_period = forms.DateTimeField(help_text = _("This date is ignored for one time only reservations."), required=False)
    
    class Meta:
        model = Reservation
        exclude = ('creator', 'created_on', 'room')
        

class OccurrenceForm(SpanForm):
    
    class Meta:
        model = Occurrence
        exclude = ('original_start', 'original_end', 'reservation', 'cancelled')


class RuleForm(forms.ModelForm):
    params = forms.CharField(widget=forms.Textarea, help_text=_("Extra parameters to define this type of recursion. Should follow this format: rruleparam:value;otherparam:value."))

    def clean_params(self):
        params = self.cleaned_data["params"]
        try:
            Rule(params=params).get_params()
        except (ValueError, SyntaxError):
            raise forms.ValidationError(_("Params format looks invalid"))
        return self.cleaned_data["params"]
