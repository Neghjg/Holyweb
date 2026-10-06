from django.contrib import admin

from .models import Factory, FactoryUser, WorkVolume


@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "external_id")
    readonly_fields = ("external_id",)
    search_fields = ("name",)


@admin.register(FactoryUser)
class FactoryUserAdmin(admin.ModelAdmin):
    list_display = ("user", "factory")
    autocomplete_fields = ("factory",)
    raw_id_fields = ("user",)


@admin.register(WorkVolume)
class WorkVolumeAdmin(admin.ModelAdmin):
    list_display = ("factory", "start", "finish", "weight", "created")
    list_filter = ("factory",)

    # Written only through plan.services (it also appends to tsDB), so read-only here.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
