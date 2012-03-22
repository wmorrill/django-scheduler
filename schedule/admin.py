from django.contrib import admin
from schedule.forms import RuleForm

from schedule.models import Room, Reservation, RoomRelation, Rule

class RoomAdminOptions(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ['name']

class RuleAdmin(admin.ModelAdmin):
    form = RuleForm

admin.site.register(Room, RoomAdminOptions)
admin.site.register(Rule, RuleAdmin)
admin.site.register([Reservation, RoomRelation])
