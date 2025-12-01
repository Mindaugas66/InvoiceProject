from django.urls import path
from .views import clients, overview, new_invoice, remove_line_item, user_invoices, invoice_preview, my_info, upload_invoice, calculate_taxes_ajax
from .auth_views import user_login, user_logout

urlpatterns = [
    # Authentication
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    
    # Main app views
    path('', overview, name='overview'),
    path('new-invoice/', new_invoice, name='new_invoice'),
    path('remove-line-item/', remove_line_item, name='remove_line_item'),
    path('user-invoices/', user_invoices, name='user_invoices'),
    path('upload-invoice/', upload_invoice, name='upload_invoice'),
    path('invoice/<int:invoice_id>/preview/', invoice_preview, name='invoice_preview'),
    path('my-info/', my_info, name='my_info'),
    path('clients/', clients, name='clients'),
    path('calculate-taxes/', calculate_taxes_ajax, name='calculate_taxes'),
]