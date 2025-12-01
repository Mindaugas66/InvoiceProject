from num2words import num2words
from invoices.models import Invoice
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum
import re

def generate_invoice_number(user_id=None):
    """
    Generate a sequential invoice number as an integer string with leading zeros (e.g., 00000001).
    Finds the latest invoice for the given user and increments its number by 1.
    If user_id is None, falls back to all invoices.
    """
    digit_count = 8

    if user_id:
        last_invoice = Invoice.objects.filter(user_id=user_id).order_by('-id').first()
    else:
        last_invoice = Invoice.objects.order_by('-id').first()

    if not last_invoice or not last_invoice.invoice_number:
        return '1'.zfill(digit_count)

    last_number = last_invoice.invoice_number
    # Strip all non-digit characters to get the numeric part
    numeric_part_str = re.sub(r'\D', '', last_number)

    try:
        numeric_part = int(numeric_part_str)
        next_number = numeric_part + 1
        new_invoice_number = str(next_number).zfill(digit_count)
        return new_invoice_number
    except (ValueError, IndexError):
        return '1'.zfill(digit_count)
    

def amount_to_words(amount):
    """
    Convert a number to words in Lithuanian using num2words,
    formatted as '<words> eur ir <cents> ct'.
    """
    try:
        amount = float(amount)
        euros = int(amount)
        cents = int(round((amount - euros) * 100))
        words = num2words(euros, lang='lt')
        return f"{words} eur ir {cents:02d} ct"
    except Exception as e:
        print(f"num2words error: {e}")
        return ""

def get_invoices_for_user_year(user_id, year):
    return Invoice.objects.filter(user_id=user_id, date__year=year)

def get_total_gross_income(user_id, year):
    invoices = get_invoices_for_user_year(user_id, year)
    return invoices.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

def calculate_taxes(income, expenses=None, use_30_percent_rule=True, activity_start_date=None, current_date=None, psd_self_paid=True):
    """
    Calculate Lithuanian self-employment taxes according to official rules.
    
    Args:
        income: Total income (P) in euros
        expenses: Actual expenses (I). If None and use_30_percent_rule=True, calculated as 30% of income
        use_30_percent_rule: If True, use 30% expense rule
        activity_start_date: Date when individual activity started (for VSDI exemption)
        current_date: Current calculation date (defaults to today)
        psd_self_paid: If True, user pays PSD monthly themselves (excludes from total tax calculation) - DEFAULT TRUE
    
    Returns:
        Dictionary with all tax calculations
        
    Note: This is a simplified annual calculation. For accurate monthly PSD, use calculate_monthly_psd()
    """
    from datetime import datetime, timedelta
    
    if current_date is None:
        current_date = datetime.now().date()
    
    # Tax rates and constants (2025)
    VSDI_RATE = Decimal('0.1252')  # 12.52%
    PSDI_RATE = Decimal('0.0698')   # 6.98%
    GPM_RATE = Decimal('0.05')      # 5%
    GPM_LIMIT = Decimal('11900.00') # Only up to €11,900 is taxed at 5%
    MMA_2025 = Decimal('1038.00')   # Minimal monthly salary 2025
    MIN_PSD_MONTHLY = Decimal('72.45')  # Minimal PSD per month if income <= MMA
    
    income = Decimal(str(income))
    
    # Calculate expenses
    if use_30_percent_rule:
        expenses = (income * Decimal('0.30')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        expenses = Decimal(str(expenses)) if expenses else Decimal('0.00')
    
    # Calculate profit
    profit = (income - expenses).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # VSDI and PSDI base = 50% of profit
    vsdi_base = (profit * Decimal('0.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    psdi_base = (profit * Decimal('0.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Check first-year VSDI exemption
    vsdi_exempt = False
    if activity_start_date:
        months_since_start = ((current_date.year - activity_start_date.year) * 12 + 
                             (current_date.month - activity_start_date.month))
        vsdi_exempt = months_since_start < 12
    
    # Calculate VSDI (0 if first-year exemption applies)
    vsdi = Decimal('0.00') if vsdi_exempt else (vsdi_base * VSDI_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Calculate PSDI with special logic
    psdi_is_self_paid = False
    psdi_note = ""
    
    if psd_self_paid:
        # User pays PSD monthly themselves
        psdi_is_self_paid = True
        
        # Calculate monthly average income
        monthly_income = (income / Decimal('12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if monthly_income <= MMA_2025:
            # Use minimal PSD payment × 12 months
            psdi = MIN_PSD_MONTHLY * Decimal('12')
            psdi_note = f"Minimalus savaimokestis {MIN_PSD_MONTHLY}€/mėn × 12 mėn (vid. pajamos {monthly_income}€/mėn ≤ MMA)"
        else:
            # Calculate annual PSD: 6.98% of PSDI base
            # This represents what you should pay monthly based on declared base to Sodra
            monthly_psdi_base = (psdi_base / Decimal('12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            monthly_psdi = (monthly_psdi_base * PSDI_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            psdi = monthly_psdi * Decimal('12')  # Annual total
            psdi_note = f"Savaimokestis {monthly_psdi}€/mėn × 12 mėn (vid. pajamos {monthly_income}€/mėn > MMA)"
    else:
        # Normal PSDI calculation
        monthly_income = (income / Decimal('12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if monthly_income <= MMA_2025:
            # Use minimal PSD payment × 12 months
            psdi = MIN_PSD_MONTHLY * Decimal('12')
            psdi_note = f"Minimalus PSD {MIN_PSD_MONTHLY}€/mėn × 12 mėn"
        else:
            # Standard calculation - annual
            psdi = (psdi_base * PSDI_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            psdi_note = "Standartinis metinis skaičiavimas"
    
    # Calculate GPM base
    # If PSD is self-paid, don't deduct it from GPM base
    if psdi_is_self_paid:
        gpm_base = (profit - vsdi).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        gpm_base = (profit - vsdi - psdi).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Apply GPM limit (only up to €11,900 is taxed)
    gpm_taxable = min(gpm_base, GPM_LIMIT)
    gpm = (gpm_taxable * GPM_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Calculate total taxes
    # If PSD is self-paid, it's not included in the total to deduct
    if psdi_is_self_paid:
        total_taxes = (vsdi + gpm).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_taxes_display = (vsdi + psdi + gpm).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        total_taxes = (vsdi + psdi + gpm).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_taxes_display = total_taxes
    
    # Calculate net income
    net_income = (income - expenses - total_taxes).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return {
        'income': income,
        'expenses': expenses,
        'profit': profit,
        'vsdi_base': vsdi_base,
        'psdi_base': psdi_base,
        'vsdi': vsdi,
        'psdi': psdi,
        'psdi_is_self_paid': psdi_is_self_paid,
        'psdi_note': psdi_note,
        'gpm_base': gpm_base,
        'gpm_taxable': gpm_taxable,
        'gpm': gpm,
        'total_taxes': total_taxes_display,  # For display purposes
        'total_taxes_to_deduct': total_taxes,  # Actual amount to deduct from income
        'net_income': net_income,
        'vsdi_exempt': vsdi_exempt,
        'income_vs_mma': 'below' if income <= MMA_2025 else 'above',
        'mma_2025': float(MMA_2025),
        'min_psd_monthly': float(MIN_PSD_MONTHLY),
        'gpm_percent': float((gpm / income * 100).quantize(Decimal('0.01'))) if income > 0 else 0,
        'vsdi_percent': float((vsdi / income * 100).quantize(Decimal('0.01'))) if income > 0 else 0,
        'psdi_percent': float((psdi / income * 100).quantize(Decimal('0.01'))) if income > 0 else 0,
        'total_percent': float((total_taxes_display / income * 100).quantize(Decimal('0.01'))) if income > 0 else 0,
    }


def calculate_monthly_psd(monthly_invoices_data, use_30_percent_rule=True):
    """
    Calculate PSD month by month based on actual monthly income.
    Each month is calculated independently against MMA threshold.
    
    Args:
        monthly_invoices_data: List of tuples (month_number, monthly_income)
        use_30_percent_rule: If True, use 30% expense rule
    
    Returns:
        Dictionary with monthly breakdown and annual total
    """
    MMA_2025 = Decimal('1038.00')
    MIN_PSD_MONTHLY = Decimal('72.45')
    PSDI_RATE = Decimal('0.0698')
    
    monthly_psd_breakdown = []
    annual_psd_total = Decimal('0.00')
    
    for month_num, income in monthly_invoices_data:
        income = Decimal(str(income))
        
        # Calculate monthly profit
        if use_30_percent_rule:
            expenses = (income * Decimal('0.30')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            expenses = Decimal('0.00')
        
        profit = (income - expenses).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        psdi_base = (profit * Decimal('0.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Check if this month's income is above MMA
        if income <= MMA_2025:
            # Use minimal PSD
            monthly_psd = MIN_PSD_MONTHLY
            calculation_type = "minimal"
        else:
            # Calculate based on actual income
            monthly_psd = (psdi_base * PSDI_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            # But never less than minimum
            if monthly_psd < MIN_PSD_MONTHLY:
                monthly_psd = MIN_PSD_MONTHLY
                calculation_type = "minimal"
            else:
                calculation_type = "calculated"
        
        annual_psd_total += monthly_psd
        
        monthly_psd_breakdown.append({
            'month': month_num,
            'income': float(income),
            'profit': float(profit),
            'psdi_base': float(psdi_base),
            'psd': float(monthly_psd),
            'calculation_type': calculation_type,
            'above_mma': income > MMA_2025
        })
    
    return {
        'monthly_breakdown': monthly_psd_breakdown,
        'annual_total': float(annual_psd_total),
        'mma_2025': float(MMA_2025),
        'min_psd_monthly': float(MIN_PSD_MONTHLY)
    }

def get_total_taxes(user_id, year):
    """Legacy function - uses simplified 30% rule calculation"""
    gross = get_total_gross_income(user_id, year)
    if gross == 0:
        return {
            'gpm': Decimal('0.00'),
            'vsd': Decimal('0.00'),
            'psd': Decimal('0.00'),
            'total': Decimal('0.00'),
            'gpm_percent': 0,
            'vsd_percent': 0,
            'psd_percent': 0,
            'total_percent': 0,
        }
    
    # Use the new calculation function
    result = calculate_taxes(gross, use_30_percent_rule=True)
    
    return {
        'gpm': result['gpm'],
        'vsd': result['vsdi'],  # Map vsdi to vsd for backward compatibility
        'psd': result['psdi'],  # Map psdi to psd for backward compatibility
        'total': result['total_taxes'],
        'gpm_percent': result['gpm_percent'],
        'vsd_percent': result['vsdi_percent'],
        'psd_percent': result['psdi_percent'],
        'total_percent': result['total_percent'],
    }

def get_net_income(user_id, year):
    gross = get_total_gross_income(user_id, year)
    taxes = get_total_taxes(user_id, year)
    return (gross - taxes['total']).quantize(Decimal('0.01'))

def get_invoice_stats(user_id, year):
    invoices = get_invoices_for_user_year(user_id, year)
    total = invoices.count()
    paid = invoices.filter(status='paid').count() if hasattr(Invoice, 'status') else 0
    unpaid = total - paid
    return {'total': total, 'paid': paid, 'unpaid': unpaid}