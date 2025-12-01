"""
Authentication views for the invoices application.
Handles user login and logout functionality.
"""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages


def user_login(request):
    """
    Handle user login.
    GET: Display login form
    POST: Authenticate user and redirect to overview
    """
    # Redirect if already authenticated
    if request.user.is_authenticated:
        return redirect('overview')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Validate input
        if not username or not password:
            messages.error(request, 'Įveskite prisijungimo vardą ir slaptažodį.')
            return render(request, 'auth/login.html')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Sveiki sugrįžę, {user.username}!')
            
            # Redirect to next page or overview
            next_url = request.GET.get('next', 'overview')
            return redirect(next_url)
        else:
            messages.error(request, 'Neteisingas prisijungimo vardas arba slaptažodis.')
    
    return render(request, 'auth/login.html')


@login_required
def user_logout(request):
    """
    Handle user logout.
    Logs out the user and redirects to login page.
    """
    logout(request)
    messages.info(request, 'Sėkmingai atsijungėte.')
    return redirect('login')
