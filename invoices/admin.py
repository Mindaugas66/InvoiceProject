from django.contrib import admin
from .models import Client, SelfInfo, Invoice, LineItem, TaxSettings

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'first_name', 'last_name', 'phone', 'company_code')
    search_fields = ('company_name', 'first_name', 'last_name', 'company_code', 'pvm_code')
    list_filter = ('company_name',)
    ordering = ('company_name',)

@admin.register(SelfInfo)
class SelfInfoAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'email', 'phone', 'activity_start_date')
    search_fields = ('first_name', 'last_name', 'email', 'individual_code')
    list_filter = ('user', 'activity_start_date')

@admin.register(TaxSettings)
class TaxSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'use_30_percent_rule', 'actual_expenses')
    list_filter = ('use_30_percent_rule',)
    search_fields = ('user__username',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'user', 'client', 'date', 'pay_until', 'total_amount', 'serija')
    search_fields = ('invoice_number', 'client__company_name', 'user__username')
    list_filter = ('user', 'date', 'serija', 'client')
    date_hierarchy = 'date'
    ordering = ('-date',)
    readonly_fields = ('total_amount',)
    
    fieldsets = (
        ('Pagrindinė informacija', {
            'fields': ('serija', 'invoice_number', 'user', 'client')
        }),
        ('Datos', {
            'fields': ('date', 'pay_until')
        }),
        ('Finansai', {
            'fields': ('total_amount',)
        }),
    )

@admin.register(LineItem)
class LineItemAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'invoice', 'quantity', 'pcs_type', 'price', 'total_amount')
    search_fields = ('service_name', 'invoice__invoice_number')
    list_filter = ('pcs_type', 'invoice__date')
    ordering = ('-invoice__date',)
