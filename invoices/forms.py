from django import forms
from invoices.models import Client, Invoice, SelfInfo

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['serija', 'client', 'invoice_number', 'date', 'pay_until']
        widgets = {
            'serija': forms.Select(attrs={'class': 'input-field'}),
            'invoice_number': forms.TextInput(attrs={'class': 'input-field'}),
            'date': forms.DateInput(attrs={'class': 'input-field'}),
            'pay_until': forms.DateInput(attrs={'class': 'input-field'}),
            'client': forms.Select(attrs={'class': 'input-field'}),
        }

class SelfInfoForm(forms.ModelForm):
    class Meta:
        model = SelfInfo
        fields = ['first_name', 'last_name', 'individual_code', 'address', 'phone', 'bank_account', 'activity_start_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input-field'}),
            'first_name': forms.TextInput(attrs={'class': 'input-field'}),
            'last_name': forms.TextInput(attrs={'class': 'input-field'}),
            'individual_code': forms.TextInput(attrs={'class': 'input-field'}),
            'address': forms.TextInput(attrs={'class': 'input-field'}),
            'phone': forms.TextInput(attrs={'class': 'input-field'}),
            'bank_account': forms.TextInput(attrs={'class': 'input-field'}),
            'activity_start_date': forms.DateInput(attrs={'class': 'input-field', 'type': 'date'}),
        }
        labels = {
            'activity_start_date': 'Veiklos pradžios data (VSDI lengvatai)',
        }

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['company_name', 'company_code', 'pvm_code', 'address', 'first_name', 'last_name', 'phone']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'input-field'}),
            'company_code': forms.TextInput(attrs={'class': 'input-field'}),
            'pvm_code': forms.TextInput(attrs={'class': 'input-field'}),
            'address': forms.TextInput(attrs={'class': 'input-field'}),
            'first_name': forms.TextInput(attrs={'class': 'input-field'}),
            'last_name': forms.TextInput(attrs={'class': 'input-field'}),
            'phone': forms.TextInput(attrs={'class': 'input-field'}),
        }