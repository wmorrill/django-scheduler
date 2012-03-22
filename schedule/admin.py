from django.contrib import admin
from schedule.forms import RuleForm

from schedule.models import Calendar, Event, CalendarRelation, Rule

# from guardian.admin import GuardedModelAdmin

class CalendarAdminOptions(admin.ModelAdmin):
# class CalendarAdminOptions(GuardedModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ['name']
	
class RuleAdmin(admin.ModelAdmin):
    form = RuleForm

admin.site.register(Calendar, CalendarAdminOptions)
admin.site.register(Rule, RuleAdmin)
admin.site.register([Event, CalendarRelation])
