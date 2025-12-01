from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from decimal import Decimal
import json
from .models import Client, Invoice, LineItem, SelfInfo, TaxSettings
from .forms import ClientForm, InvoiceForm, SelfInfoForm
from .utils import (
    amount_to_words,
    generate_invoice_number,
    get_total_gross_income,
    get_total_taxes,
    get_net_income,
    get_invoice_stats,
    calculate_taxes,
)
import uuid
import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_POST


@login_required
def overview(request):
    # Use the currently logged-in user
    current_user = request.user
    
    # Default to current year
    year = int(request.GET.get('year', datetime.date.today().year))
    # Years for dropdown (last 5 years)
    years = list(range(datetime.date.today().year, datetime.date.today().year - 5, -1))

    # Get financial data for the logged-in user
    gross_income = get_total_gross_income(current_user.id, year)
    net_income = get_net_income(current_user.id, year)
    taxes = get_total_taxes(current_user.id, year)
    invoice_stats = get_invoice_stats(current_user.id, year)

    # Calculate growth compared to previous year
    prev_gross = get_total_gross_income(current_user.id, year - 1)
    prev_net = get_net_income(current_user.id, year - 1)
    gross_income_growth = (
        ((gross_income - prev_gross) / prev_gross * 100) if prev_gross > 0 else 100 if gross_income > 0 else 0
    )
    net_income_growth = (
        ((net_income - prev_net) / prev_net * 100) if prev_net > 0 else 100 if net_income > 0 else 0
    )
    taxes_percent = (taxes['total'] / gross_income * 100) if gross_income > 0 else 0

    # Invoice stats percentages
    total = invoice_stats['total'] or 1
    invoice_stats['total_percent'] = 100
    invoice_stats['paid_percent'] = round(invoice_stats['paid'] / total * 100, 2)
    invoice_stats['unpaid_percent'] = round(invoice_stats['unpaid'] / total * 100, 2)

    # Monthly data for charts
    monthly_data = []
    month_names = ['Sau', 'Vas', 'Kov', 'Bal', 'Geg', 'Bir', 'Lie', 'Rgp', 'Rgs', 'Spa', 'Lap', 'Gru']
    
    for month in range(1, 13):
        month_invoices = Invoice.objects.filter(
            user_id=current_user.id,
            date__year=year,
            date__month=month
        )
        month_income = sum(inv.total_amount for inv in month_invoices)
        month_taxes = get_total_taxes(current_user.id, year)
        # Calculate proportional taxes for the month
        if gross_income > 0:
            month_tax_amount = (month_income / gross_income) * taxes['total']
        else:
            month_tax_amount = Decimal('0.00')
        
        monthly_data.append({
            'month': month_names[month - 1],
            'income': float(month_income),
            'taxes': float(month_tax_amount),
            'net': float(month_income - month_tax_amount)
        })

    context = {
        'active_page': 'overview',
        'year': year,
        'years': years,
        'gross_income': gross_income,
        'net_income': net_income,
        'taxes': taxes,
        'invoice_stats': invoice_stats,
        'gross_income_growth': round(gross_income_growth, 2),
        'net_income_growth': round(net_income_growth, 2),
        'taxes_percent': round(taxes_percent, 2),
        'monthly_data': json.dumps(monthly_data),  # Convert to JSON string
        # Optionally add due dates if you want to show them in the table
        'gpm_due_date': None,
        'vsd_due_date': None,
        'psd_due_date': None,
    }
    return render(request, 'overview.html', context)

@login_required
def new_invoice(request):
    # Handle POST requests
    if request.method == 'POST':
        # Handle different form submissions
        if 'add_line_item' in request.POST:
            return _add_line_item(request)
        elif 'create_invoice' in request.POST:
            return _create_invoice(request)

        return redirect('new_invoice')

    # Handle GET requests
    # Initialize session data if not present
    if 'invoice_data' not in request.session:
        request.session['invoice_data'] = {
            'client': '',
            'date': datetime.date.today().strftime('%Y-%m-%d'),
            'pay_until': (datetime.date.today() + datetime.timedelta(days=14)).strftime('%Y-%m-%d'),
            'line_items': []
        }

    # Generate invoice number for the logged-in user
    invoice_number = generate_invoice_number(user_id=request.user.id)

    # Get data from session
    invoice_data = request.session.get('invoice_data', {})

    # Prepare initial data for form
    initial_data = {
        'serija': invoice_data.get('serija', 'AA'),
        'client': invoice_data.get('client', ''),
        'invoice_number': invoice_data.get('invoice_number', invoice_number),
        'date': invoice_data.get('date', datetime.date.today().strftime('%Y-%m-%d')),
        'pay_until': invoice_data.get('pay_until', (datetime.date.today() + datetime.timedelta(days=14)).strftime('%Y-%m-%d'))
    }

    # Create form with initial data
    form = InvoiceForm(initial=initial_data)

    # Get clients for dropdown
    clients = Client.objects.all()

    # Get line items from session
    line_items = invoice_data.get('line_items', [])

    # Calculate total amount
    total_amount = Decimal('0.00')
    for item in line_items:
        total_amount += Decimal(item.get('total_amount', '0'))

    context = {
        'form': form,
        'clients': clients,
        'selected_client': invoice_data.get('client', ''),
        'invoice_number': invoice_data.get('invoice_number', invoice_number),
        'date': invoice_data.get('date', ''),
        'pay_until': invoice_data.get('pay_until', ''),
        'line_items': line_items,
        'total_amount': total_amount,
        'active_page': 'new_invoice',
    }

    return render(request, 'new_invoice.html', context)


def _add_line_item(request):
    service_name = request.POST.get('new_service_name')
    quantity = request.POST.get('new_quantity')
    pcs_type = request.POST.get('new_pcs_type')
    price = request.POST.get('new_price')

    if service_name and quantity and price:
        try:
            quantity = Decimal(quantity)
            price = Decimal(price)
            total = quantity * price

            # Generate a temporary ID for this item
            item_id = str(uuid.uuid4())

            # Add to session
            line_items = request.session['invoice_data'].get('line_items', [])
            line_items.append({
                'id': item_id,
                'service_name': service_name,
                'quantity': str(quantity),
                'pcs_type': pcs_type,
                'price': str(price),
                'total_amount': str(total)
            })
            request.session['invoice_data']['line_items'] = line_items

            # Update other form fields in session
            request.session['invoice_data'].update({
                'client': request.POST.get('client', ''),
                'date': request.POST.get('date', ''),
                'pay_until': request.POST.get('pay_until', '')
            })
            request.session.modified = True
        except (ValueError, TypeError):
            pass  # Handle invalid number inputs

    return redirect('new_invoice')


def _create_invoice(request):
    serija = request.POST.get('serija', 'AA')
    client_id = request.POST.get('client')
    invoice_number = request.POST.get('invoice_number')
    date = request.POST.get('date')
    pay_until = request.POST.get('pay_until')
    line_items = request.session['invoice_data'].get('line_items', [])

    if client_id and invoice_number and date and pay_until and line_items:
        try:
            with transaction.atomic():
                total_amount = sum(Decimal(item['total_amount']) for item in line_items)
                invoice = Invoice.objects.create(
                    serija=serija,
                    user_id=request.user.id,  # Use logged-in user
                    client_id=client_id,
                    invoice_number=invoice_number,
                    date=date,
                    pay_until=pay_until,
                    total_amount=total_amount
                )
                for item in line_items:
                    LineItem.objects.create(
                        invoice=invoice,
                        service_name=item['service_name'],
                        quantity=item['quantity'],
                        pcs_type=item['pcs_type'],
                        price=item['price'],
                        total_amount=item['total_amount']
                    )
                if 'invoice_data' in request.session:
                    del request.session['invoice_data']
                return redirect('user_invoices')
        except Exception as e:
            print(e)
            return redirect('user_invoices')
    return redirect('user_invoices')

@login_required
def remove_line_item(request):
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        if item_id and 'invoice_data' in request.session:
            line_items = request.session['invoice_data'].get('line_items', [])
            request.session['invoice_data']['line_items'] = [item for item in line_items if item['id'] != item_id]
            request.session.modified = True

    return redirect('new_invoice')

@login_required
def user_invoices(request):
    # Get invoices for the logged-in user only
    invoices = Invoice.objects.filter(user=request.user).order_by('-date')
    clients = Client.objects.all().order_by('company_name')
    
    context = {
        'invoices': invoices,
        'clients': clients,
        'active_page': 'all_invoices',
    }
    return render(request, 'user_invoices.html', context)

@login_required
def invoice_preview(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    line_items = invoice.line_items.all()  # Use the related_name
    client = invoice.client
    amount_in_words = amount_to_words(invoice.total_amount)
    context = {
        'invoice': invoice,
        'client': client,
        'line_items': line_items,
        'amount_in_words': amount_in_words,
    }
    return render(request, 'invoice_preview.html', context)

@login_required
def my_info(request):
    # Get or create self_info for the logged-in user
    self_info, _ = SelfInfo.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = SelfInfoForm(request.POST, instance=self_info)
        if form.is_valid():
            form.save()
            return redirect('my_info')
    else:
        form = SelfInfoForm(instance=self_info)
    
    context = {
        'form': form,
        'active_page': 'my_info',
    }
    return render(request, 'my_info.html', context)

@login_required
def clients(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('clients')
    else:
        form = ClientForm()
    clients_list = Client.objects.all()
    context = {
        'form': form,
        'clients': clients_list,
        'active_page': 'clients',
    }
    return render(request, 'clients.html', context)

@login_required
def upload_invoice(request):
    if request.method == 'POST':
        try:
            client_id = request.POST.get('client')
            invoice_number = request.POST.get('invoice_number')
            month = request.POST.get('month')  # Format: YYYY-MM
            total_amount = Decimal(request.POST.get('total_amount'))
            
            # Parse month to get date (use first day of month)
            year, month_num = month.split('-')
            invoice_date = datetime.date(int(year), int(month_num), 1)
            
            # Calculate payment due date (30 days from invoice date)
            pay_until = invoice_date + datetime.timedelta(days=30)
            
            # Get client
            client = get_object_or_404(Client, id=client_id)
            
            # Create invoice
            invoice = Invoice.objects.create(
                user=request.user,
                client=client,
                invoice_number=invoice_number,
                date=invoice_date,
                pay_until=pay_until,
                total_amount=total_amount
            )
            
            return redirect('user_invoices')
        except Exception as e:
            # Handle errors gracefully
            return redirect('user_invoices')
    
    return redirect('user_invoices')


@login_required
def calculate_taxes_ajax(request):
    """AJAX endpoint for real-time tax calculations"""
    if request.method == 'POST':
        try:
            income = Decimal(request.POST.get('income', '0'))
            use_30_percent = request.POST.get('use_30_percent', 'true') == 'true'
            expenses = Decimal(request.POST.get('expenses', '0')) if not use_30_percent else None
            year = request.POST.get('year', None)  # Optional year for monthly breakdown
            
            # PSD is always self-paid as a global rule
            psd_self_paid = True
            
            # Get user's activity start date
            self_info = SelfInfo.objects.filter(user=request.user).first()
            activity_start_date = self_info.activity_start_date if self_info else None
            
            # If year is provided, calculate PSD month by month from actual invoices
            monthly_psd_data = None
            if year:
                try:
                    year = int(year)
                    monthly_invoices = []
                    
                    for month in range(1, 13):
                        month_invoices = Invoice.objects.filter(
                            user_id=request.user.id,
                            date__year=year,
                            date__month=month
                        )
                        month_income = sum(inv.total_amount for inv in month_invoices)
                        monthly_invoices.append((month, month_income))
                    
                    # Calculate monthly PSD
                    from .utils import calculate_monthly_psd
                    monthly_psd_data = calculate_monthly_psd(monthly_invoices, use_30_percent)
                    
                except Exception as e:
                    # If monthly calculation fails, fall back to annual average
                    monthly_psd_data = None
            
            # Calculate taxes
            result = calculate_taxes(
                income=income,
                expenses=expenses,
                use_30_percent_rule=use_30_percent,
                activity_start_date=activity_start_date,
                psd_self_paid=psd_self_paid
            )
            
            # If we have monthly PSD data, override the PSDI value
            if monthly_psd_data:
                result['psdi'] = Decimal(str(monthly_psd_data['annual_total']))
                result['psdi_note'] = f"Savaimokestis skaičiuojamas kiekvieną mėnesį pagal faktines pajamas (suma: {monthly_psd_data['annual_total']}€/metus)"
                result['psdi_monthly_breakdown'] = monthly_psd_data['monthly_breakdown']
                
                # Recalculate totals with the accurate monthly PSD
                result['total_taxes'] = result['vsdi'] + result['psdi'] + result['gpm']
                result['total_taxes_to_deduct'] = result['vsdi'] + result['gpm']  # PSD not deducted
                result['net_income'] = income - result['expenses'] - result['total_taxes_to_deduct']
            
            # Convert Decimal to float for JSON
            json_result = {
                k: float(v) if isinstance(v, Decimal) else v 
                for k, v in result.items()
            }
            
            return JsonResponse(json_result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
