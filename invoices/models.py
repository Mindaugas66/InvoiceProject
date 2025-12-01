from django.db import models
from django.contrib.auth import get_user_model


class Client(models.Model):
    company_name = models.CharField(max_length=255)
    company_code = models.CharField(max_length=50)
    pvm_code = models.CharField(max_length=50, blank=True, null=True)
    address = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.company_name} ({self.first_name} {self.last_name})"

class SelfInfo(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='self_info')
    title = models.CharField(max_length=100, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    individual_code = models.CharField(max_length=50)
    email = models.CharField(blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=30)
    bank_account = models.CharField(max_length=100)
    activity_start_date = models.DateField(null=True, blank=True, help_text="Individualios veiklos pradžios data (VSDI lengvatai)")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class TaxSettings(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='tax_settings')
    use_30_percent_rule = models.BooleanField(default=True, help_text="Naudoti 30% išlaidų taisyklę")
    actual_expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Faktinės išlaidos (jei nenaudojama 30% taisyklė)")
    
    def __str__(self):
        return f"Tax settings for {self.user.username}"


class Invoice(models.Model):
    SERIJA_CHOICES = [
        ('AA', 'AA'),
        ('VSP', 'VSP'),
    ]
    serija = models.CharField(max_length=3, choices=SERIJA_CHOICES, default='AA')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    date = models.DateField()
    pay_until = models.DateField()
    invoice_number = models.CharField(max_length=50)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.client}"

class LineItem(models.Model):
    PCS_TYPE_CHOICES = [
        ('val', 'val'),
        ('vnt', 'Vnt'),
    ]
    invoice = models.ForeignKey(Invoice, related_name='line_items', on_delete=models.CASCADE)
    service_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    pcs_type = models.CharField(max_length=3, choices=PCS_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.service_name} ({self.quantity} {self.get_pcs_type_display()})"

